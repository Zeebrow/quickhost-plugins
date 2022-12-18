from setuptools import setup, find_packages

setup(
    name='quickhost-null',
    verstion='0.0.1',
    package_dir={'':'src'},
    packages=find_packages(where='src'),
    install_requires=[],
    entry_points={
        "quickhost_plugin": [
            'null_app=quickhost_null:load_plugin',
            'null_parser=quickhost_null:get_parser',
        ]
    },
    scripts=[
        'scripts/quickhost-null.py'
    ]

)
