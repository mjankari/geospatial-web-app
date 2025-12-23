import sys
import os
import importlib.util
import multiprocessing # <--- 1. Import this
from qgis.core import QgsApplication, QgsProcessingProvider

# --- DEFINE YOUR PROVIDER CLASS OUTSIDE THE MAIN BLOCK ---
# This needs to be readable by the background processes when they import the file.
class TempAlgProvider(QgsProcessingProvider):
    def __init__(self, alg_instance):
        super().__init__()
        self.alg = alg_instance

    def loadAlgorithms(self):
        self.addAlgorithm(self.alg)

    def id(self) -> str:
        return 'custom_standalone'

    def name(self) -> str:
        return 'Custom Standalone Provider'

    def icon(self):
        return QgsProcessingProvider.icon(self)

# --- EXECUTION GUARD ---
if __name__ == '__main__':
    # 2. Recommended for Windows to prevent certain freeze errors
    multiprocessing.freeze_support() 

    # 3. Initialize QGIS (Only run this once!)
    qgs = QgsApplication([], False)
    qgs.initQgis()

    import processing
    from processing.core.Processing import Processing
    Processing.initialize()

    # --- LOAD CUSTOM SCRIPT ---
    script_path = r'C:\Users\User\AppData\Roaming\QGIS\QGIS3\profiles\default\processing\scripts\scp-classification.py'

    spec = importlib.util.spec_from_file_location("scp_classification", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["scp_classification"] = module
    spec.loader.exec_module(module)

    my_alg = module.Classification()

    # --- REGISTER PROVIDER ---
    provider = TempAlgProvider(my_alg)
    QgsApplication.processingRegistry().addProvider(provider)

    full_alg_id = f"{provider.id()}:{my_alg.name()}"
    print(f"Algorithm registered: {full_alg_id}")

    # --- RUN THE ALGORITHM ---
    params = {
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

    processing.run(full_alg_id, params)

    print("Classification finished successfully!")
    qgs.exitQgis()