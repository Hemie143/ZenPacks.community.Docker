from importlib import import_module


def optional_import(module_name, patch_module_name):
    """Import patch_module_name only if module_name is importable."""
    try:
        import_module(module_name)
    except ImportError:
        pass
    else:
        import_module('.{0}'.format(patch_module_name), 'ZenPacks.community.Docker.patches')


optional_import('Products.ZenModel', 'platform')
