import os
from .logger import DualLogger
from .utils import parse_arguments, md2html, html2pdf
from .tools import Tools
from .conversation import Conversation
from .config import Config

if os.path.exists(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "bedrock_wrapper.py")
):
    from .bedrock_wrapper import BedrockModel
else:
    from .bedrock import BedrockModel
