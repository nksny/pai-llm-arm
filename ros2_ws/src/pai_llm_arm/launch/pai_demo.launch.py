import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    params = os.path.join(get_package_share_directory('pai_llm_arm'), 'config', 'params.yaml')
    return LaunchDescription([
        Node(package='pai_llm_arm', executable='perception', name='perception', parameters=[params], output='screen'),
        Node(package='pai_llm_arm', executable='planner', name='planner', parameters=[params], output='screen'),
        Node(package='pai_llm_arm', executable='controller', name='controller', parameters=[params], output='screen'),
        Node(package='pai_llm_arm', executable='monitor', name='monitor', parameters=[params], output='screen'),
    ])
