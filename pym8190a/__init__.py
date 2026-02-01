import numpy as np
np.set_printoptions(linewidth=500, suppress=True)

# Import submodules that don't require hardware
from . import elements
from . import elements as el
from . import util
from . import settings

# Import hardware-dependent modules only if dependencies are available
try:
    from . import hardware
    from . import hardware as hw
    from .pym8190a import *
except (ImportError, ModuleNotFoundError):
    # Allow package to be imported without hardware dependencies for testing
    pass