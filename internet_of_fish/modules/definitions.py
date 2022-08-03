import os, logging, posixpath
from glob import glob

# constant paths
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.dirname(MODULE_DIR)
BASE_DIR = os.path.dirname(CODE_DIR)
MODELS_DIR = os.path.join(BASE_DIR, 'models')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
SUMMARY_LOG_FILE = os.path.join(LOG_DIR, 'SUMMARY.log')
CREDENTIALS_DIR = os.path.join(BASE_DIR, 'credentials')
RESOURCES_DIR = os.path.join(BASE_DIR, 'resources')
HOME_DIR = os.path.expanduser('~')
DATA_DIR = os.path.join(HOME_DIR, 'CichlidPiData', '__ProjectData')
CLOUD_HOME_DIR = 'cichlidVideo:/BioSci-McGrath/Apps'
CLOUD_DATA_DIR = posixpath.join(CLOUD_HOME_DIR, 'CichlidPiData', '__ProjectData')
END_FILE = os.path.join(HOME_DIR, 'ENTER_END_MODE')
PAUSE_FILE = os.path.join(HOME_DIR, 'HARD_SHUTDOWN')
SENDGRID_KEY_FILE = os.path.join(CREDENTIALS_DIR, 'sendgrid_key.secret')


# variable paths
def PROJ_DIR(proj_id, analysis_state=None):
    """if the analysis_state argument is provided, this function will construct the path to the local project directory
    whether or not it currently exists. If analysis_state is not provided, this function will infer it by searching
    for a project with the correct project ID and assuming the analysis state is the name of the parent directory.
    If analysis_state is not provided and a local copy of the project does not already exist, a FileNotFound error will
    be raised."""
    if analysis_state:
        return os.path.join(DATA_DIR, analysis_state, proj_id)
    ret = glob(os.path.join(DATA_DIR, '**', proj_id))
    if not ret:
        raise FileNotFoundError
    return ret[0]


def PROJ_VID_DIR(proj_id, analysis_state=None):
    return os.path.join(PROJ_DIR(proj_id, analysis_state), 'Videos')


def PROJ_IMG_DIR(proj_id, analysis_state=None):
    return os.path.join(PROJ_DIR(proj_id, analysis_state), 'Images')


def PROJ_LOG_DIR(proj_id, analysis_state=None):
    return os.path.join(PROJ_DIR(proj_id, analysis_state), 'Logs')


def PROJ_JSON_FILE(proj_id, analysis_state=None):
    return os.path.join(PROJ_DIR(proj_id, analysis_state), f'{proj_id}.json')
