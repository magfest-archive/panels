from uber.common import *
from panels._version import __version__
from panels.config import *
from panels.models import *
import panels.model_checks
from panels.automated_emails import *

static_overrides(join(panels_config['module_root'], 'static'))
template_overrides(join(panels_config['module_root'], 'templates'))
mount_site_sections(panels_config['module_root'])


from panels.notifications import *  # noqa: E402
from panels.sep_commands import *  # noqa: E402
