class ToolRegistry:
    """
    Реестр инструментов агента.

    Позже сюда добавим:
    - поиск по базе знаний;
    - работу с 1С;
    - диагностику;
    - Bitrix24;
    - другие инструменты.
    """

    def __init__(self):
        self._tools = {}

    def register(self, name: str, tool):
        self._tools[name] = tool

    def get(self, name: str):
        return self._tools.get(name)

    def all(self) -> dict:
        return self._tools.copy()