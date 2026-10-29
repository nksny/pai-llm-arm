from setuptools import setup
from glob import glob
package_name = 'pai_llm_arm'
setup(
    name=package_name, version='0.1.0', packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml') + glob('config/*.config')),
        ('share/' + package_name + '/worlds', glob('worlds/*.sdf')),
    ],
    install_requires=['setuptools', 'anthropic'], zip_safe=True,
    entry_points={'console_scripts': [
        'planner = pai_llm_arm.planner_node:main',
        'controller = pai_llm_arm.controller_node:main',
        'monitor = pai_llm_arm.monitor_node:main',
        'perception = pai_llm_arm.perception_node:main',
        'perception_camera = pai_llm_arm.perception_camera_node:main',
    ]},
)
