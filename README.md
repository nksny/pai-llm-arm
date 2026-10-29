# PAI最終課題: 自然言語指示によるCRANE+ V2のピック&プレース（LLMプランナー＋閉ループ再計画）

Physical AI応用1講座 最終課題の作業ディレクトリ。

## 構成

```
pai-final-task/
├── docker/            コンテナ起動スクリプト（講義イメージ ros2-desktop-ai-robot-book-humble を使用）
├── ros2_ws/src/pai_llm_arm/   自作ROS2パッケージ（提出対象）
│   ├── pai_llm_arm/
│   │   ├── planner_node.py     自然言語 → サブゴール列（LLM, Claude API）
│   │   ├── controller_node.py  サブゴール → 関節/グリッパ指令（CRANE+ V2）
│   │   ├── monitor_node.py     到達判定・失敗検知 → 再計画要求
│   │   └── perception_node.py  物体座標の取得（Gazebo真値 / 余力でVLM）
│   ├── launch/pai_demo.launch.py       4ノードの一括起動
│   ├── launch/demo_gazebo.launch.py    Gazebo + CRANE+ V2 を録画向けGUI設定(1280x720, 固定カメラ)で起動
│   └── config/params.yaml, gui.config
├── scripts/           ワールド配置・ノード起動・指示送信の補助スクリプト（コンテナ内で実行）
├── docs/              レポート草稿・構成図
├── videos/            提出動画の素材・完成品（Gitには含めない）
└── logs/              LLM入出力・実行ログ（提出時は個人情報が無いことを確認）
```

## 起動手順

1. `pai-final-task/.env` に `ANTHROPIC_API_KEY=sk-ant-...` を書く（gitignore済）
2. コンテナ起動: `bash docker/run.sh`（初回）/ `docker start pai`（2回目以降）
3. ブラウザで http://localhost:6080 を開く
4. コンテナ内ターミナル（`docker exec -it -u ubuntu pai bash`）で
   ```bash
   pip3 install -U anthropic brotli             # 初回のみ(古いbrotliだとSDKが接続エラーになる)
   cd ~/pai_work/pai-final-task/ros2_ws && colcon build --symlink-install
   ros2 launch pai_llm_arm demo_gazebo.launch.py   # 別ターミナル(Ignition Gazebo + CRANE+ V2)
   # (講義パッケージ標準の起動: ros2 launch crane_plus_gazebo no_moveit_crane_plus_with_table.launch.py でも可)
   cd ~/pai_work/pai-final-task
   bash scripts/setup_world.sh      # 色付きブロックとトレイを配置
   bash scripts/start_nodes.sh      # perception / controller / monitor / planner を起動
   bash scripts/say.sh "赤いブロックを青いトレイに置いて"
   ros2 topic echo /monitor/result  # 成否
   bash scripts/reset_world.sh      # やり直し
   ```
5. デモの録画（コンテナ内, ffmpeg で Gazebo ウィンドウを x11grab）
   ```bash
   bash scripts/run_demo.sh basic   "赤いブロックを青いトレイに置いて"          # videos/basic.mp4
   bash scripts/run_demo.sh recover "赤いブロックを緑のトレイに置いて" 20       # 20秒後に赤ブロックを動かし再計画を誘発
   bash scripts/cam.sh 0.48 -0.40 1.42 0.08 0.04 1.10                           # GUIカメラを位置→注視点で指定
   bash scripts/annotate.sh recover 2       # 字幕(指示文・計画中・妨害・再計画・結果)を焼き込み、2倍速版を作る
   ```
   `run_demo.sh` は録画と同時にイベント時刻を `videos/<name>.events` に記録し、終了時に字幕入り `videos/<name>_sub.mp4` も生成する。
6. 提出動画の組み立て: `python3 scripts/make_final.py`（4本のデモからタイトル・章カード付きの `videos/final.mp4` を生成。レポート PDF は `python3 scripts/build_pdf.py`。どちらもコンテナ内で `pip3 install markdown weasyprint` が必要）

## トピック構成

```
/task/instruction (String)  ─→ planner ─→ /plan/subgoals (JSON) ─→ controller ─→ /crane_plus_*_controller/joint_trajectory
/perception/objects (JSON)  ─→ planner, monitor          /controller/status ─→ monitor ─→ /monitor/replan ─→ planner
```

- 座標はロボット base_link 基準 [m]（x前方, y左, z上, テーブル面 z=0）。perception は Ignition の `/world/default/pose/info` 真値から変換
- `/monitor/result` には最終結果(success/failure)のみ流れる。再計画の経過は `/monitor/status` と各ノードのログ(`/tmp/*.log`)
- 録画中は CPU 競合でシミュレーション速度が実時間の5〜7割に落ちるため、controller は `use_sim_time` でステップを刻む

## 提出ルール（講義要項より）

- レポートPDF: `説明資料_PAI最終課題_<omnicampusアカウント名>.pdf`
- GitHub: public。講義イメージやCRANE+パッケージは含めず、本ディレクトリのみ
- 動画: 1〜3分、タイトル `PAI最終課題_<omnicampusアカウント名>`、限定公開以上
- 氏名・所属・メールアドレスを成果物に含めない。APIキーは環境変数のみ
