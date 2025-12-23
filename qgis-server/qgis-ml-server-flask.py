import sys
import os
import importlib.util
import multiprocessing
import json
import boto3  # <--- AWS SDK
from pathlib import Path
from flask import Flask, request, jsonify
from qgis.core import (
    QgsApplication, 
    QgsProcessingContext, 
    QgsProcessingFeedback
)

# --- 1. CONFIGURATION ---
app = Flask(__name__)

# Global variable to hold the SINGLE instance of your algorithm
LOADED_ALG = None 

# --- AWS CONFIGURATION ---
S3_BUCKET_NAME = os.environ.get("MY_S3_BUCKET_NAME", "default-bucket-name")

# Initialize S3 Client without hardcoded keys
# It will automatically pick up the credentials from the environment variables 
# we will set in the .bat file.
s3_client = boto3.client('s3')

DEFAULT_PARAMS = {
    'BAND_INPUT_LAYERS': [
        'C:/Users/User/OneDrive/Desktop/GIS-ML/london-lulc/processed-clipped/clipRT_T30UXC_A053745_20251006T110612_B02.tif',
        'C:/Users/User/OneDrive/Desktop/GIS-ML/london-lulc/processed-clipped/clipRT_T30UXC_A053745_20251006T110612_B03.tif',
        'C:/Users/User/OneDrive/Desktop/GIS-ML/london-lulc/processed-clipped/clipRT_T30UXC_A053745_20251006T110612_B04.tif',
        'C:/Users/User/OneDrive/Desktop/GIS-ML/london-lulc/processed-clipped/clipRT_T30UXC_A053745_20251006T110612_B05.tif',
        'C:/Users/User/OneDrive/Desktop/GIS-ML/london-lulc/processed-clipped/clipRT_T30UXC_A053745_20251006T110612_B06.tif',
        'C:/Users/User/OneDrive/Desktop/GIS-ML/london-lulc/processed-clipped/clipRT_T30UXC_A053745_20251006T110612_B07.tif',
        'C:/Users/User/OneDrive/Desktop/GIS-ML/london-lulc/processed-clipped/clipRT_T30UXC_A053745_20251006T110612_B08.tif',
        'C:/Users/User/OneDrive/Desktop/GIS-ML/london-lulc/processed-clipped/clipRT_T30UXC_A053745_20251006T110612_B8A.tif',
        'C:/Users/User/OneDrive/Desktop/GIS-ML/london-lulc/processed-clipped/clipRT_T30UXC_A053745_20251006T110612_B11.tif',
        'C:/Users/User/OneDrive/Desktop/GIS-ML/london-lulc/processed-clipped/clipRT_T30UXC_A053745_20251006T110612_B12.tif'
    ],
    'TRAINING_INPUT_SCPX': r'C:\Users\User\OneDrive\Desktop\GIS-ML\london-lulc\london-lulc-macroclass-only-training.scpx',
    'TESTING_INPUT_SCPX': 'C:/Users/User/OneDrive/Desktop/GIS-ML/london-lulc/testing.gpkg',
    'USE_MACROCLASS': True,
    'MC_OR_CLASS_FIELD': 'macroclass_id',
    'NODATA': None,
    'NORMALIZATION': None,
    'ML_MODEL': 2,
    'SINGLE_THRESHOLD': None,
    'SIGNATURE_THRESHOLD': False,
    'SAVE_SIGNATURE': False,
    'CALCULATE_CONFIDENCE': False,
    'MLP_LAYERS': '100',
    'MLP_MAX_ITER': 200,
    'MLP_ACTIVATION': 'relu',
    'MLP_APLHA': 0.01,
    'MLP_TRAIN_PORTION': 0.9,
    'MLP_BATCH_SIZE': 'auto',
    'MLP_LEARNING_RATE_INIT': 0.001,
    'CROSS_VALIDATION': False,
    'RF_TREES': 10,
    'RF_SPLIT': 2,
    'RF_MAX_FEATURES': '',
    'RF_ONE_VS_REST': False,
    'SVM_REGULARIZATION': 1,
    'SVM_KERNEL': 'rbf',
    'SVM_GAMMA': 'scale',
    'FIND_BEST_ESTIMATOR': None,
    'BALANCED_CLASS_WEIGHT': False,
    'CLASSIFIER_INPUT_RSMO': '',
    'RASTER_OUTPUT': 'TEMPORARY_OUTPUT',
    'CLASSIFICATION_FOLDER': r'C:\Users\User\OneDrive\Desktop\GIS-ML\london-lulc'
}

# --- 2. HELPER FUNCTIONS ---
def upload_folder_to_s3(local_folder_path, s3_bucket):
    """
    Recursively uploads a folder and its contents to S3.
    Preserves the folder name as the S3 prefix.
    """
    folder = Path(local_folder_path)
    if not folder.exists():
        print(f"Warning: Folder {local_folder_path} does not exist. Skipping upload.")
        return

    print(f"Starting upload for folder: {folder.name}")
    
    # Walk through all files in the directory
    for file_path in folder.rglob('*'):
        if file_path.is_file():
            # Create S3 Key: FolderName/FileName (e.g., RandomForest-2025/classification.tif)

            # relative_to(folder.parent) keeps the main folder name in the S3 path
            # We manually add 'data_storage/' at the beginning of the path
            s3_key = f"data_storage/{file_path.relative_to(folder.parent)}".replace("\\", "/")
            
            print(f"Uploading {file_path.name} -> s3://{s3_bucket}/{s3_key}")
            try:
                s3_client.upload_file(str(file_path), s3_bucket, s3_key)
            except Exception as e:
                print(f"Failed to upload {file_path.name}: {e}")

# --- 3. FLASK ROUTE ---
@app.route('/ml-request', methods=['POST'])
def ml_request():
    global LOADED_ALG
    if not LOADED_ALG:
        return jsonify({"error": "QGIS Algorithm not loaded"}), 500

    try:
        user_params = request.get_json() or {}
        print(f"Received request. Overriding {len(user_params)} parameters.")

        # Merge defaults with user params
        final_params = DEFAULT_PARAMS.copy()
        final_params.update(user_params)

        # --- DIRECT EXECUTION ---
        context = QgsProcessingContext()
        feedback = QgsProcessingFeedback()

        # Run the algorithm
        results, success = LOADED_ALG.run(final_params, context, feedback)

        if success:
            # 1. Get the path to the output raster (e.g., .../RandomForest-Date/classification.tif)
            raster_output = results.get('RASTER_OUTPUT')
            
            # 2. Derive the parent folder path (e.g., .../RandomForest-Date)
            # We do this because the script creates a folder, puts files in it, and returns the file path.
            if raster_output and os.path.exists(raster_output):
                output_folder = os.path.dirname(raster_output)
                
                # 3. Upload the entire folder to S3
                upload_folder_to_s3(output_folder, S3_BUCKET_NAME)
                
                upload_status = "Uploaded to S3"
            else:
                upload_status = "Skipped S3 (Output path invalid)"

            return jsonify({
                "status": "success",
                "message": f"Classification complete. {upload_status}",
                "result": results
            })
        else:
            return jsonify({
                "status": "failure",
                "message": "Algorithm reported failure"
            }), 500

    except Exception as e:
        print(f"Error during processing: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- 4. SETUP FUNCTION ---
def setup_qgis_and_algorithm():
    """Initializes QGIS and loads the algorithm instance."""
    qgs = QgsApplication([], False)
    qgs.initQgis()

    import processing
    from processing.core.Processing import Processing
    Processing.initialize()

    # Load Custom Script Manually
    script_path = r'C:\Users\User\AppData\Roaming\QGIS\QGIS3\profiles\default\processing\scripts\scp-classification.py'
    
    spec = importlib.util.spec_from_file_location("scp_classification", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["scp_classification"] = module
    spec.loader.exec_module(module)

    # Instantiate the class
    alg_instance = module.Classification()
    alg_instance.initAlgorithm()
    
    print(f"Algorithm '{alg_instance.name()}' loaded and initialized directly.")
    
    return qgs, alg_instance

# --- 5. MAIN ENTRY POINT ---
if __name__ == '__main__':
    multiprocessing.freeze_support()

    print("Initializing QGIS Engine...")
    qgs_instance, alg_instance = setup_qgis_and_algorithm()
    
    # Set the global variable
    LOADED_ALG = alg_instance

    print("Starting Flask Server on port 5000...")
    # threaded=False is REQUIRED for QGIS stability
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=False)

    qgs_instance.exitQgis()