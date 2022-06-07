from setuptools import setup, find_packages

setup(
    name='quickhost_azure',
    version='0.0.1',
    package_dir={'':'src'},
    packages=find_packages(where='src'),
    install_requires=[
        'boto3'
    ],
    entry_points={
        "quickhost_plugin": ['quickhost_azure=quickhost_azure:load_plugin']
    }
)
