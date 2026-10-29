# 引き継ぎメモ（2026-10-30 作業分）

次回セッションの最初に読む。CLAUDE.md（方針・環境の実測値）と合わせて使う。

## 1. 現在の到達点

動画の4段構成すべてを Claude Code から録画済み。素材は `videos/{basic,ambiguous,recover,sort}.mp4`（git 管理外, 1280x720, 30fps, 各50〜100秒）と、
字幕（指示文・LLM計画中・実行中・妨害・再計画・完了）を焼き込んだ `videos/*_sub.mp4`。`scripts/annotate.sh <name> 2` で2倍速・「2倍速」表記付きも作れる。

| デモ | 指示 | 結果（10/29 録画） |
|---|---|---|
| 基本 | 赤いブロックを青いトレイに置いて | 成功（約45秒） |
| 曖昧 | 青いブロックを同じ色のトレイに置いて | 成功（青トレイを選択） |
| 妨害復帰 | 赤いブロックを緑のトレイに置いて → 把持2秒後に赤ブロックを移動 | monitor 検知 → 再計画1回 → 成功（約90秒。再計画が2回必要になる回もある） |
| 仕分け | ブロックを色ごとに同じ色のトレイに仕分けて | 成功（赤→赤トレイ, 青→青トレイ。黄色は「対応するトレイが無いので残す」とLLMが判断, 約85秒） |

GitHub: https://github.com/nksny/pai-llm-arm（public, ブランチ master）。push 済み。10/30 に一度提出済み（差し替え可）。

### 10/30 の追加
- **カメラ知覚** `perception_camera_node.py`: `worlds/table_camera.sdf`（Sensors システム＋真下向き固定カメラ, テーブル上 0.70 m, hfov 0.9）の
  `/overhead_camera/image` を HSV 色分割 → 連結成分 → ピンホール逆投影。真値との誤差 ≤2 mm（`scripts/check_camera.py`）。
  `demo_gazebo.launch.py` は既定でカメラ付きワールド（`camera:=false` で講義標準）。`PERCEPTION=camera bash scripts/start_nodes.sh` で切替。
- **繰り返し評価** `scripts/eval_batch.sh <rounds> <tag>` → `logs/eval.jsonl`、`scripts/eval_summary.py <tag>` で表。
- **controller**: 所要時間 = 最大関節移動量 / 0.5 rad/s（下限 2 s）。把持中は置き位置を接線方向 −1.2 cm 補正（片側固定指のため）。
- **monitor**: トレイ自身を「置かれた物体」と誤認するバグを修正（`container_keyword`）。許容 0.035 m。
- 初期配置: 赤ブロックを (0.10, 0.05) に（旧 (0.12, 0.06) は緑トレイの角に乗って 22° 傾いていた）。
- 動画: `run_demo.sh` はカメラ知覚時にデバッグ画像も `videos/<name>_cam.mp4` に録り、`annotate.sh` が右下に PiP で重ねる。

## 2. 再開手順（コンテナが残っている場合）

```bash
docker start pai                                   # 母機
docker exec -it -u ubuntu pai bash                 # 以降コンテナ内
export DISPLAY=:0
ros2 launch pai_llm_arm demo_gazebo.launch.py &    # 録画向けGUI設定で Gazebo (noVNC http://localhost:6080)
cd ~/pai_work/pai-final-task
bash scripts/setup_world.sh      # ブロック3個・トレイ3枚(青/緑/赤)を配置(再実行可)
PERCEPTION=camera bash scripts/start_nodes.sh   # 4ノード起動（カメラ知覚。.env のAPIキーを自動で読む）
python3 scripts/check_camera.py  # 知覚の誤差確認
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
  monitor とのマッチだけで終了して planner に届かなかった。`say.sh` は `-w 2` で2購読者を待ち、さらに 10/30 からは `-t 2` で
  2 回送る（評価 20 回中 1 回、planner に届かなかった）。planner は 5 秒以内の同一指示を無視する。
- **controller の done は動作完了後に出す**（10/30）。以前は最後の指令送信時に出していたため、カメラ知覚では腕が物体を隠した
  瞬間に monitor が判定して偽の再計画が起きた。
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

- 到達範囲ぎりぎり（r≈0.20）のトレイでは把持姿勢が 30° 傾く。置き位置の補正（接線 −1.2cm, 傾き比例で手前へ）後の誤差は約 1cm。monitor の許容は 0.035m。
- 妨害や滑落でブロックが r>0.22 に出ると planner が「計画不可」を返す（設計どおり）。評価での残る失敗はこれ。
- 開いたグリッパや前腕が隣のブロック（7cm 程度の距離）を掃くことがある。配置はこれ以上詰めない。
- 1回のデモでも planner の応答に 6〜20秒かかる（opus）。動画では編集でカットするか2倍速にする。
- 提出物に氏名・所属・メール・APIキーを含めない。git の author は `pai <noreply@example.com>` にしてある。

## 5. 評価結果（logs/eval.jsonl, git 管理外）

- `truth`（10/30 朝, 修正前）: 19/20（うち 1 回は monitor のトレイ誤認による偽成功）
- `camera`（カメラ知覚, 補正なし）: 20/24 → 置き位置ずれが主因
- `final2`（最終構成）: 19/20。失敗 1 回は指示未達（LLM 呼び出し 0）。レポート 5.2 節に掲載。

## 6. 次回やること（優先順）

1. 10/30 にカメラ知覚＋小窓付きで4本撮り直し済み（`videos/*_sub.mp4`、旧版は `videos/_old1029/`）。
2. 提出動画は `videos/final.mp4`（2分43秒, 1280x720, 無音, 仕分け・妨害は 2.5 倍速）。`python3 scripts/make_final.py` で再生成（タイトル＋構成図 → ①基本 → ②曖昧 → ③仕分け → ④妨害復帰 → 工夫点と今後。実行区間は2倍速で右上に表記）。YouTube にタイトル `PAI最終課題_<omnicampusアカウント名>` で限定公開以上、子ども向け「いいえ」。
3. レポートを推敲（`docs/report.md` → コンテナ内で `python3 scripts/build_pdf.py` → `docs/report.pdf`）。提出時に `説明資料_PAI最終課題_<omnicampusアカウント名>.pdf` にリネーム。
4. GitHub public リポジトリ作成 → push → README 最終確認。
