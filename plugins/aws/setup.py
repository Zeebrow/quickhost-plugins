from setuptools import setup, find_packages

setup(
    # the Distribution Name for the package
    # https://packaging.python.org/en/latest/glossary/#term-Distribution-Package
    name='quickhost-aws', 
    version='0.0.1',
    package_dir={'':'src'},
    packages=find_packages(where='src'),
    install_requires=[
        'boto3',
        'quickhost'
    ],
    #depends_on=
    entry_points={
        "quickhost_plugin": ['quickhost_aws=quickhost_aws:load_plugin']
    }
)
