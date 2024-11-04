from PyQt6.QtWidgets import QWidget


class WidgetRegistry:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(WidgetRegistry, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "registered_widgets"):
            self.registered_widgets: dict[str, QWidget] = {}

    def register(self, widget: QWidget, object_name: str):
        widget.setObjectName(object_name)
        if object_name not in self.registered_widgets:
            self.registered_widgets[object_name] = widget

    def get_widget_by_id(self, object_name: str):
        return self.registered_widgets.get(object_name, None)

    def get_registered_widgets(self):
        return self.registered_widgets

    def get_all_registered_ids(self):
        return list(self.registered_widgets.keys())


widget_registry = WidgetRegistry()
