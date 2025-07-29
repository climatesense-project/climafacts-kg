from dotenv import load_dotenv
from platformdirs import user_data_path
from usingversion import getattr_with_version

APPNAME = "climafactskg"
APP_REPOSITORY = "https://github.com/climatesense-project/climafacts-kg"
DEFAULT_ROOT_PATH = user_data_path(appname=APPNAME)

__getattr__ = getattr_with_version(APPNAME, __file__, __name__)

load_dotenv()
