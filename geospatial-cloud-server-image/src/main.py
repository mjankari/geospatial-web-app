import json
import os
import boto3
import base64 # Added missing import for PNG encoding 🛰️
import rasterio
import geopandas as gpd
import numpy as np
from rasterio.warp import transform_bounds

# Fixed: Added trailing comma to make this a proper tuple for .endswith() 
VECTOR_FILES = ('.geojson', '.gpkg', '.shp')
RASTER_FILES = ('.tif',) 

# Initialize the S3 client outside the handler
s3 = boto3.client('s3')

# We'll get this from our Docker run command (locally) 
# or Lambda configuration (in AWS)
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

def get_s3_file_structure(bucket_name, folder_name):
    """
    Lists S3 objects under a prefix and organizes them into 
    a dictionary: { "run_id": ["file1.tif", "file2.geojson"] }
    """
    try:
        # 1. List objects with the prefix (e.g., 'data_storage/')
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=f"{folder_name}/")
        
        if 'Contents' not in response:
            return {}, None
            
        structure = {}
        for obj in response['Contents']:
            key = obj['Key']
            # Split key: ['data_storage', 'run_id', 'filename']
            key_parts = [p for p in key.split('/') if p]
            
            # We expect a structure like folder_name/run_id/file_name
            if len(key_parts) >= 3:
                # Based on your structure, index 1 is run_id, index 2 is file_name
                run_id = key_parts[1]
                file_name = key_parts[2]
                
                if run_id not in structure:
                    structure[run_id] = []
                structure[run_id].append(file_name)
                
        return structure, None
    except Exception as e:
        return None, str(e)

def get_metadata(local_path):
    """
    Reads the TIF file header (using Rasterio), extracts bounds, 
    and transforms them to EPSG:4326 (the web standard).
    """
    try:
        with rasterio.open(local_path) as src:
            # 1. Transform the bounds from the TIF's native CRS to EPSG:4326
            wgs84_bounds = transform_bounds(
                src_crs=src.crs, 
                dst_crs='EPSG:4326', 
                left=src.bounds.left, 
                bottom=src.bounds.bottom, 
                right=src.bounds.right, 
                top=src.bounds.top
            )

            # 2. Package the reprojected bounds for the client
            return {
                # We return the bounds in the required [W, S, E, N] format
                "bounds": list(wgs84_bounds), 
                "crs": f'original: {src.crs.to_string()}, converted to EPSG:4326',
                "file_type": "raster"
            }, None
            
    except Exception as e:
        return None, str(e)


def process_tif_to_png(file_path):
    """
    Reads TIF, scales data (1-4 range to 0-255) ignoring NoData, 
    and writes a temporary PNG.
    """
    if not os.path.exists(file_path):
        return None, "Raster source file not found."

    # Using your descriptive naming convention 🖼️
    temp_png_path = file_path + "_temp_output.png"

    try:
        with rasterio.open(file_path) as src:
            # 1. Read the array and get the NoData value
            image_array = src.read(1) # read first band of tif
            nodata_val = src.nodata
            
            # Exclude NoData from min/max calculations 🔢
            if nodata_val is not None:
                valid_data = np.ma.masked_equal(image_array, nodata_val)
                min_val, max_val = np.min(valid_data), np.max(valid_data)
            else:
                min_val, max_val = np.min(image_array), np.max(image_array)

            # 2. Check the data range (should be 1 to 4)
            range_val = max_val - min_val
            if range_val <= 0:
                 return None, "TIF data is uniform and cannot be scaled."

            # 3. Apply the scaling: (data - min) / (range) * 255
            # This scales the 1-4 range to 0-255
            image_array_scaled = ((image_array - min_val) / range_val) * 255

            # 4. Convert to 8-bit integer type
            image_array_8bit = image_array_scaled.astype(np.uint8)

            # 5. Re-apply the NoData mask to the 8-bit array (setting NoData pixels to 0)
            if nodata_val is not None:
                image_array_8bit[image_array == nodata_val] = 0 
            
            out_profile = src.profile
            out_profile.update(
                dtype=rasterio.uint8, 
                count=1,        # Single band (Grayscale)
                driver='PNG', 
                nodata=0)

            with rasterio.open(temp_png_path, 'w', **out_profile) as dst:
                dst.write(image_array_8bit, 1)
            
        return temp_png_path, None
    
    except Exception as e:
        return None, f"Error processing TIF: {e}"


def get_geojson_data(file_path):
    """
    Reads the vector file (GPKG/SHP/GeoJSON), converts it to WGS84,
    and returns a dictionary for the Lambda response.
    """
    if not os.path.exists(file_path):
        return None, "Vector source file not found."
    
    try:
        # 1. Read the vector file into a GeoDataFrame
        gdf = gpd.read_file(file_path)
        
        # 2. FORCE CONVERSION to WGS84 (EPSG:4326) 🌎
        # This ensures the coordinates work with web map libraries
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs(epsg=4326)
        
        # 3. Convert to GeoJSON string and then back to a dictionary
        geojson_str = gdf.to_json()
        geo_data_dict = json.loads(geojson_str)
        
        return geo_data_dict, None
    
    except Exception as e:
        return None, f"Error processing vector file: {e}"
    

def lambda_handler(event, context):
    # 1. Parse the request from API Gateway
    params = event.get('pathParameters', {}) or {}
    proxy_string = params.get('proxy', '')

    parts = [p for p in proxy_string.split('/') if p] # Clean up any empty strings

    # Set standard headers for CORS and JSON
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*"
    }

    # --- NEW ROUTE: get-file-structure (e.g., /api/get-file-structure/data_storage) ---
    if len(parts) == 3 and parts[1] == "get-file-structure":
        folder_name = parts[2]
        data, error = get_s3_file_structure(BUCKET_NAME, folder_name)
        if error:
            return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": error})}
        return {"statusCode": 200, "headers": headers, "body": json.dumps(data)}

    # --- EXISTING ROUTES: Metadata and Data Processing ---
    if len(parts) < 3:
        return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "Invalid URL structure."})}

    file_name = parts[-1]
    run_id = parts[-2]
    # Join everything before the run_id to get the 'command' path (e.g., 'api/metadata')
    command_path = '/'.join(parts[:-2])

    # Construct the S3 Key (path in the bucket)
    s3_key = f"data_storage/{run_id}/{file_name}"
    
    # Define where to save it locally in the container
    local_path = f"/tmp/{run_id}_{file_name}"

    try:
        # 2. Download from S3 to /tmp
        s3.download_file(BUCKET_NAME, s3_key, local_path)

        # 3. Route to your existing processing functions

        # --- METADATA PATH ---
        if command_path == "api/metadata" and file_name.endswith(RASTER_FILES): 
            metadata_dict, error = get_metadata(local_path)
            os.remove(local_path) # Clean up metadata source

            if error:
                return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": error})}

            return {"statusCode": 200, "headers": headers, "body": json.dumps(metadata_dict)}

        elif command_path == "api/get-data": 
            
            # --- RASTER PATH ---
            if file_name.endswith(RASTER_FILES):
                png_path, error = process_tif_to_png(local_path)
                
                if error:
                    if os.path.exists(local_path): os.remove(local_path)
                    return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": error})}

                # 4. Convert PNG to Base64
                with open(png_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

                # 5. Cleanup local files
                os.remove(local_path)
                os.remove(png_path)

                return {
                    "statusCode": 200,
                    "headers": {**headers, "Content-Type": "image/png"},
                    "body": encoded_string,
                    "isBase64Encoded": True
                }
        
            # --- VECTOR PATH ---
            elif file_name.endswith(VECTOR_FILES):
                geo_data, error = get_geojson_data(local_path)
                os.remove(local_path)

                if error:
                    return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": error})}

                return {"statusCode": 200, "headers": headers, "body": json.dumps(geo_data)}
            
            # --- INVALID FILE EXTENSION ---
            if os.path.exists(local_path): os.remove(local_path)
            return {"statusCode": 404, "headers": headers, "body": json.dumps({"error": "Unsupported extension"})}
        
        # Cleanup and error if no routes matched
        if os.path.exists(local_path): os.remove(local_path)
        return {"statusCode": 404, "headers": headers, "body": json.dumps({"error": "Unsupported route"})}

    except Exception as e:
        if os.path.exists(local_path): os.remove(local_path)
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}