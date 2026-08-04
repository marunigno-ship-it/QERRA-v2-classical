from setuptools import setup
import os
from glob import glob

package_name = 'qerra_core'

setup(
    name=package_name,
    version='2.0.0',
    py_modules=[
        'ros2_bridge',
        'ethical_core',
        'vectors',
    ],
    packages=['hsr', 'values'],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Marussa Metocharaki',
    maintainer_email='marunigno@gmail.com',
    description='QERRA-v2 Classical node executors',
    license='AGPL-3.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'bridge = ros2_bridge:main',
        ],
    },
)
