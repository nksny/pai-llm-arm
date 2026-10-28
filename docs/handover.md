# 引き継ぎメモ（2026-10-28 作業分）

次回セッションの最初に読む。CLAUDE.md（方針・環境の実測値）と合わせて使う。

## 1. 現在の到達点

動画の4段構成すべてが Claude Code からの操作で動作確認済み。

| デモ | 指示 | 結果 |
|---|---|---|
| 基本 | 赤いブロックを青いトレイに置いて | 成功（LLM計画 11ステップ, 約8秒） |
| 曖昧 | 青いブロックを同じ色のトレイに置いて | 成功（青トレイを選択） |
| 妨害復帰 | 赤いブロックを緑のトレイに置いて → 把持後にブロックを移動 | monitor が検知 → 再計画 → 成功 |
| 未試験 | 色ごとに仕分けて（複数物体） | 次回確認 |

git は `pai-final-task/` で初期化済み、3コミット。GitHub への push はまだ（リポジトリ未作成）。

## 2. 再開手順（コンテナが残っている場合）

```bash
docker start pai                                   # 母機
docker exec -it -u ubuntu pai bash                 # 以降コンテナ内
export DISPLAY=:0
ros2 launch crane_plus_gazebo no_moveit_crane_plus_with_table.launch.py &   # Gazebo (noVNC http://localhost:6080)
cd ~/pai_work/pai-final-task
bash scripts/setup_world.sh      # ブロック・トレイ配置
bash scripts/start_nodes.sh      # 4ノード起動（.env のAPIキーを自動で読む）
bash scripts/say.sh "赤いブロックを青いトレイに置いて"
ros2 topic echo /monitor/result
```

コンテナを作り直した場合は `bash docker/run.sh` の後、コンテナ内で
`pip3 install -U anthropic brotli` と `cd ros2_ws && colcon build --symlink-install` を先に実行する。

Claude Code から操作する場合は `docker exec -u ubuntu -e DISPLAY=:0 pai bash -c '...'` で同じコマンドを流せる。
ノードのログは `/tmp/{perception,controller,monitor,planner}.log`、LLM入出力は `logs/llm.jsonl`。

## 3. 初日に判明したこと（CLAUDE.md にも記載）

- Gazebo は Ignition Fortress。perception は `ign topic -e -t /world/default/pose/info -n 1` をパースして真値を得る。
- ロボット base_link は世界座標 (0,0,1.015)。テーブル面がロボット基準 z=0、4cmブロック中心は z=0.02。
- IK はリンク長 0.0714 / 0.083 / 0.0935 / 把持点 0.11 と、関節の向き（joint2 正=前傾、joint3・4 正=後ろ）で実測一致。
- グリッパは負で開（-0.5）、正で閉（0.35）。
- SDK 接続エラーの原因はイメージ同梱の古い brotli。`pip3 install -U brotli` で解決。
- 構造化出力スキーマで配列の `minItems`/`maxItems` は使えない（400）。長さ検証はコード側。
- スクリーンショットは `DISPLAY=:0 import -window root /tmp/x.png` → `docker cp` で母機に取れる。Claude Code が画面を確認できる。
- カメラ追従は `/gui/follow` サービス。ウィンドウ最大化は手動（xdotool等が無い）。

## 4. 既知の課題・注意

- Gazebo のウィンドウが小さく、録画前に noVNC 上で手動で最大化が必要。
- controller はタイマー駆動（2.5秒刻み）で到達を待たない。デモでは問題なし。速くしたい場合は `move_duration_sec` を下げる。
- 妨害復帰の試験では再計画が2回（上限）発生して成功した。1回目の再計画が失敗した理由は未調査（テレポート先 (0.08, 0.0) が到達範囲の内側ぎりぎりだった可能性）。妨害は到達範囲内の余裕のある位置へ動かす。
- `.env` のAPIキーは会話に平文で貼られたことがある。再発行推奨。
- 提出物に氏名・所属・メール・APIキーを含めない。git の author は `pai <noreply@example.com>` にしてある。

## 5. 次回やること（優先順）

1. 「色ごとに仕分けて」など複数物体指示の確認（planner のプロンプトは1つずつ順に処理する旨を記載済み）。
2. 録画手順の確立と基本デモ1本の録画（修了ライン確保）。
3. 曖昧指示・妨害復帰の録画。
4. レポート（`docs/report_outline.md` を埋める。結果の数値は `logs/llm.jsonl` と monitor ログから）。
5. GitHub public リポジトリ作成 → push → README 最終確認。
