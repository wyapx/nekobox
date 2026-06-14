from importlib.metadata import version

__version__ = version("nekobox")


def __getattr__(name: str):
    if name == "NekoBoxAdapter":
        from .main import NekoBoxAdapter

        return NekoBoxAdapter
    raise AttributeError(name)
