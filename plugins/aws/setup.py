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
        # "group_name" : ["???"="name:function"]
        #"quickhost_plugin_apps": ['quickhost_aws_app=quickhost_aws:load_plugin'],
        #"quickhost_plugin_parsers": ['quickhost_aws_parser=quickhost_aws:get_parser']
        "quickhost_plugin": [
            'aws_app=quickhost_aws:load_plugin',
            'aws_parser=quickhost_aws:get_parser'
        ],
    }
)
