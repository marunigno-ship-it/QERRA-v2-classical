# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki

import os
from glob import glob
from setuptools import setup

package_name = "qerra_core"

setup(
    name=package_name,
    version="2.4.1",
    py_modules=[
        "verify_log",
    ],
    packages=[
        "gate",
        "hsr",
        "ros2",
    ],
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml"]),
        (
            os.path.join("share", package_name, "launch"),
            glob("launch/*.launch.py"),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Marussa Metocharaki",
    maintainer_email="marunigno@gmail.com",
    description="QERRA-v2 Classical: Three-Layer Autonomous Execution Firewall and Supervisory Gate",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "qerra_gate_node = ros2.qerra_gate_node:main",
        ],
    },
)
