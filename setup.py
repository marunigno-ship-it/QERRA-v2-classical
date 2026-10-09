from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'qerra_core'

setup(
    name=package_name,
    version='2.0.2',
    py_modules=[
        'ros2_bridge',
        'ethical_core',
        'vectors',
        'classical_analyze',
        'qerra_condition_node',
        'qerra_action_ranker_node',
        'qerra_standalone_remote_node',
    ],
    packages=[
        'hsr',
        'values',
        'values.human_centered',
        'values.ecological',
        'auth',
        'models',
        'utils',
    ],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Marussa Metocharaki',
    maintainer_email='marunigno@gmail.com',
    description='QERRA-v2 Classical — Three-Layer Supervisory Execution Guard',
    license='AGPL-3.0 and Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'bridge = ros2_bridge:main',
        ],
    },
)
