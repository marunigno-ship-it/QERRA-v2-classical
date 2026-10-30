# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Marussa Metocharaki

from setuptools import setup, find_packages

package_name = "qerra_core"

setup(
    name=package_name,
    version="2.2.1",
    py_modules=[
        "verify_log",
        "ros2_bridge",
        "ethical_core",
        "vectors",
        "classical_analyze",
        "qerra_condition_node",
        "qerra_action_ranker_node",
        "qerra_standalone_remote_node",
    ],
    packages=[
        "gate",
        "hsr",
        "values",
        "values.human_centered",
        "values.ecological",
        "auth",
        "models",
        "utils",
        "ros2",
    ],
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml"]),
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
            "bridge = ros2_bridge:main",
            "qerra_gate_node = ros2.qerra_gate_node:main",
        ],
    },
)
