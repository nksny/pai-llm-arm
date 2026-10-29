"""crane_plus_gazebo の no_moveit 版 launch を、録画向け GUI 設定(1280x720, 卓上カメラ,
サイドパネル無し)で起動する。構成は RT Corporation の launch(Apache-2.0)に準拠。"""
import os

from ament_index_python.packages import get_package_share_directory
from crane_plus_description.robot_description_loader import RobotDescriptionLoader
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetParameter


def launch_setup(context):
    use_camera = LaunchConfiguration('camera').perform(context) == 'true'
    env = {'IGN_GAZEBO_SYSTEM_PLUGIN_PATH': os.environ['LD_LIBRARY_PATH'],
           'IGN_GAZEBO_RESOURCE_PATH': os.path.dirname(
               get_package_share_directory('crane_plus_description'))}
    if use_camera:  # 俯瞰カメラ付きワールド(Sensors システム有効)
        world_file = os.path.join(
            get_package_share_directory('pai_llm_arm'), 'worlds', 'table_camera.sdf')
    else:
        world_file = os.path.join(
            get_package_share_directory('crane_plus_gazebo'), 'worlds', 'table.sdf')
    gui_config = os.path.join(
        get_package_share_directory('pai_llm_arm'), 'config', 'gui.config')
    ign_gazebo = ExecuteProcess(
        cmd=['ign gazebo -r', world_file, '--gui-config', gui_config],
        output='screen', additional_env=env, shell=True)

    loader = RobotDescriptionLoader()
    loader.use_gazebo = 'true'
    loader.use_ignition = 'true'
    loader.gz_control_config_package = 'crane_plus_control'
    loader.gz_control_config_file_path = 'config/crane_plus_controllers.yaml'
    robot_description = {'robot_description': loader.load()}

    def spawner(name):
        return ExecuteProcess(cmd=[f'ros2 run controller_manager spawner {name}'],
                              shell=True, output='screen')

    bridge_topics = ['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock']
    if use_camera:
        bridge_topics += ['/overhead_camera/image@sensor_msgs/msg/Image[ignition.msgs.Image',
                          '/overhead_camera/camera_info@sensor_msgs/msg/CameraInfo[ignition.msgs.CameraInfo']

    return [
        SetParameter(name='use_sim_time', value=True),
        ign_gazebo,
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             name='robot_state_publisher', output='both', parameters=[robot_description]),
        Node(package='ros_gz_sim', executable='create', output='screen',
             arguments=['-topic', '/robot_description', '-name', 'crane_plus',
                        '-z', '1.015', '-allow_renaming', 'true']),
        spawner('joint_state_broadcaster'),
        spawner('crane_plus_arm_controller'),
        spawner('crane_plus_gripper_controller'),
        Node(package='ros_gz_bridge', executable='parameter_bridge', output='screen',
             arguments=bridge_topics),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('camera', default_value='true',
                              description='俯瞰カメラ付きワールドを使う(camera:=false で講義標準の table.sdf)'),
        OpaqueFunction(function=launch_setup),
    ])
