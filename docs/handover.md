# 引き継ぎメモ（2026-10-29 作業分）

次回セッションの最初に読む。CLAUDE.md（方針・環境の実測値）と合わせて使う。

## 1. 現在の到達点

動画の4段構成すべてを Claude Code から録画済み。素材は `videos/{basic,ambiguous,recover,sort}.mp4`（git 管理外, 1280x720, 30fps, 各60〜160秒）。

| デモ | 指示 | 結果（10/29 録画） |
|---|---|---|
| 基本 | 赤いブロックを青いトレイに置いて | 成功（約45秒） |
| 曖昧 | 青いブロックを同じ色のトレイに置いて | 成功（青トレイを選択） |
| 妨害復帰 | 赤いブロックを緑のトレイに置いて → 把持2秒後に赤ブロックを移動 | monitor 検知 → 再計画2回 → 成功（約150秒。再計画1回目は移動後のブロックが r≈0.20 の遠い位置で把持ずれ） |
| 仕分け | ブロックを色ごとに同じ色のトレイに仕分けて | 成功（赤→赤トレイ, 青→青トレイ。黄色は「対応するトレイが無いので残す」とLLMが判断, 約85秒） |

GitHub への push はまだ（リポジトリ未作成）。

## 2. 再開手順（コンテナが残っている場合）

```bash
docker start pai                                   # 母機
docker exec -it -u ubuntu pai bash                 # 以降コンテナ内
export DISPLAY=:0
ros2 launch pai_llm_arm demo_gazebo.launch.py &    # 録画向けGUI設定で Gazebo (noVNC http://localhost:6080)
cd ~/pai_work/pai-final-task
bash scripts/setup_world.sh      # ブロック3個・トレイ3枚(青/緑/赤)を配置(再実行可)
bash scripts/start_nodes.sh      # 4ノード起動（.env のAPIキーを自動で読む）
bash scripts/run_demo.sh basic "赤いブロックを青いトレイに置いて"        # リセット→録画→指示→結果待ち→停止
bash scripts/run_demo.sh recover "赤いブロックを緑のトレイに置いて" 2    # 把持2秒後に妨害
```

コンテナを作り直した場合は `bash docker/run.sh` の後、コンテナ内で
`pip3 install -U anthropic brotli` と `cd ros2_ws && colcon build --symlink-install` を先に実行する。
`gui.config` や launch を変えたときも colcon build が必要（python ノードは symlink なので再起動のみ）。

Claude Code から操作する場合は `docker exec -u ubuntu -e DISPLAY=:0 pai bash -c '...'` で同じコマンドを流せる。
ノードのログは `/tmp/{perception,controller,monitor,planner}.log`、LLM入出力は `logs/llm.jsonl`。

## 3. 10/29 に判明したこと

- **設置高さ**: z=0.03 まで下げるとグリッパ先端がトレイに当たり、トレイが毎回1〜2cm押されて到達範囲外(0.22m)へ逃げていた。
  設置高さを z=0.045 に、トレイ質量を 3kg に変更して解決（関節トルクでは押せない）。
- **LLM の error 欄**: 実行可能でも解釈の根拠を `error` に書くことがあり controller が計画を拒否していた。
  planner は subgoals が非空なら error を無視するようにし、プロンプトにも明記した。
- **/monitor/result は最終結果のみ**。再計画の経過は `/monitor/status`。monitor 側にも `max_replans` があり、
  上限到達で `failure: ...(再計画上限)` を出す。planner が計画不可(error)を返した場合は再計画せず即 failure。
- **指示トピックの配信レース**: monitor も `/task/instruction` を購読するようにしたら `ros2 topic pub --once` が
  monitor とのマッチだけで終了して planner に届かなかった。`say.sh` は `-w 2` で2購読者を待つ。
- **録画中は RTF が 0.5〜0.7 に落ちる**（Gazebo はソフトウェア描画で CPU 占有）。controller は `use_sim_time: true` で
  ステップ間隔をシミュレーション時刻で刻むので動作は崩れない。
- **妨害のタイミング**は実時間固定だと把持の瞬間と重なって不安定。`wait_status.py` で controller の grasp を待ってから数秒後に動かす。
- **VNC のマウスカーソル**（大きな矢印/更新アイコン）がフレームバッファに描かれ録画に映る。record.sh は開始時にカーソルを
  画面右下へ退避させるが、録画中に noVNC 上でマウスを動かすと映り込む。録画中はブラウザに触らない。
- 2ブロックを同じ8cmトレイに置くのは物理的に不安定（押し出し）。赤トレイを追加し、各ブロックが1枚のトレイに対応する構成にした。
- `pkill -f` を docker exec の bash -c 文字列内で使うと自分自身を殺す（コマンド文字列にパターンが含まれる）。`[r]os2` 形式で回避。
  また母機側で docker exec を止めてもコンテナ内のプロセスは残る。`run_demo` を止めるときはコンテナ内で pkill する。
- `/gui/move_to/pose` サービスで GUI カメラを動かせる（`scripts/cam.sh 位置 注視点`）。確定した視点は `config/gui.config` に焼いてある。

## 4. 既知の課題・注意

- 到達範囲ぎりぎり（r≈0.20）のトレイでは把持姿勢が傾き、置き位置が1〜2cmずれる。monitor の許容は 0.03m。
- 開いたグリッパや前腕が隣のブロック（7cm 程度の距離）を掃くことがある。配置はこれ以上詰めない。
- 1回のデモでも planner の応答に 6〜20秒かかる（opus）。動画では編集でカットするか2倍速にする。
- `.env` のAPIキーは会話に平文で貼られたことがある。再発行推奨。
- 提出物に氏名・所属・メール・APIキーを含めない。git の author は `pai <noreply@example.com>` にしてある。

## 5. 次回やること（優先順）

1. `videos/` の4本を確認し、必要なら撮り直し（`run_demo.sh` 1本 1〜4分）。
2. 動画編集（1〜3分, 構成説明 → 基本 → 曖昧 → 妨害復帰 → 工夫点と今後。倍速は明記）。
3. レポート（`docs/report_outline.md` を埋める。結果の数値は `logs/llm.jsonl` と monitor ログから）。
4. GitHub public リポジトリ作成 → push → README 最終確認。
