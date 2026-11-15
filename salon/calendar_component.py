"""Static local Streamlit component. No CDN, external JS, frontend keys or build tool."""
from pathlib import Path
import streamlit.components.v1 as components

calendar = components.declare_component('salon_mobile_calendar_v2', path=str(Path(__file__).parent/'calendar_frontend'))
