# LMDebate - LLMディベートアプリ 設計書

## 1. 概要

### 1.1 目的
物事を考える際に、異なる立場からの議論を観察・参加することで、課題解決のための思考のヒントを得るためのツール。

3人のディベート参加者（A: 提案者X、B: 提案者Y、C: 判定者）による構造化されたディベートを実行し、各参加者をLLMまたは人間が担当できる。

### 1.2 主要機能
- 3者間ディベートの実行（A: 案X推進、B: 案Y推進、C: 判定者）
- 各参加者にLLMまたは人間を割り当て可能
- 全員LLMにして観戦モードも可能
- ディベート履歴の保存（SQLite）とMarkdownエクスポート
- 思考（内部推論）と発言（公開発言）の分離管理
- ロールプリセット管理（性格・行動指針を事前登録し選択）
- 主張へのテキスト＋添付ファイル（PDF、テキスト、画像等）対応

### 1.3 技術スタック
- **言語**: Python 3.10+
- **GUI**: Tkinter + CustomTkinter
- **データベース**: SQLite
- **LLM接続**: Azure OpenAI, Google Vertex AI (Gemini), Anthropic (Claude), Ollama, LM Studio, Llama.cpp
- **設定管理**: APIキーは`.env`、モデル設定はJSON

---

## 2. アーキテクチャ

### 2.1 全体構成

```
LMDebate/
├── main.py                     # エントリポイント
├── requirements.txt            # 依存パッケージ
├── .env.example                # 環境変数テンプレート
├── config/
│   ├── llm_providers.json      # LLMプロバイダ・モデル定義
│   ├── role_presets.json        # ロールプリセット定義
│   └── default_settings.json   # デフォルト設定
├── src/
│   ├── __init__.py
│   ├── app.py                  # アプリケーションメインクラス
│   ├── models/
│   │   ├── __init__.py
│   │   ├── debate.py           # ディベートデータモデル
│   │   ├── participant.py      # 参加者データモデル
│   │   ├── message.py          # メッセージデータモデル
│   │   ├── role_preset.py      # ロールプリセットデータモデル
│   │   ├── attachment.py       # 添付ファイルデータモデル
│   │   └── settings.py         # 設定データモデル
│   ├── services/
│   │   ├── __init__.py
│   │   ├── debate_service.py   # ディベート進行管理
│   │   ├── llm_service.py      # LLM統合インターフェース
│   │   ├── llm_providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # LLMプロバイダ基底クラス
│   │   │   ├── azure_openai.py # Azure OpenAI接続
│   │   │   ├── vertex_ai.py    # Google Vertex AI接続
│   │   │   ├── anthropic.py    # Anthropic Claude接続
│   │   │   ├── ollama.py       # Ollama接続
│   │   │   ├── lmstudio.py     # LM Studio接続
│   │   │   └── llamacpp.py     # Llama.cpp接続
│   │   ├── history_service.py  # 履歴管理（SQLite）
│   │   ├── export_service.py   # Markdownエクスポート
│   │   ├── preset_service.py   # ロールプリセット管理
│   │   └── attachment_service.py # 添付ファイル管理
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py      # メインウィンドウ
│   │   ├── setup_view.py       # ディベート設定画面
│   │   ├── debate_view.py      # ディベート実行画面
│   │   ├── history_view.py     # 履歴閲覧画面
│   │   ├── settings_view.py    # LLM設定画面
│   │   ├── preset_view.py      # ロールプリセット管理画面
│   │   └── components/
│   │       ├── __init__.py
│   │       ├── message_bubble.py   # 発言バブルUI
│   │       ├── thinking_panel.py   # 思考表示パネル
│   │       ├── participant_card.py # 参加者情報カード
│   │       ├── timer_widget.py     # タイマーウィジェット
│   │       └── file_attachment.py  # 添付ファイル選択UI
│   └── utils/
│       ├── __init__.py
│       ├── config_loader.py    # 設定読み込み
│       ├── prompt_builder.py   # LLMプロンプト構築
│       └── token_counter.py    # トークン数推定
├── data/
│   ├── debates.db              # SQLiteデータベース（自動生成）
│   └── attachments/            # 添付ファイル保存先（debate_id/で整理）
└── exports/                    # Markdownエクスポート先
```

### 2.2 レイヤー構成

```
┌─────────────────────────────────────┐
│            UI Layer (Tkinter)       │
│   setup_view / debate_view / ...    │
├─────────────────────────────────────┤
│          Service Layer              │
│  debate_service / llm_service / ... │
├─────────────────────────────────────┤
│          Model Layer                │
│  debate / participant / message     │
├─────────────────────────────────────┤
│        Infrastructure Layer         │
│  SQLite / LLM API / Config Files    │
└─────────────────────────────────────┘
```

---

## 3. データモデル

### 3.1 ロールプリセット（RolePreset）

設定画面で事前に登録しておき、ディベート開始時に各参加者に割り当てる。

| フィールド | 型 | 説明 |
|---|---|---|
| id | str (UUID) | プリセットID |
| name | str | プリセット名（例: 「慎重な分析者」） |
| role_description | str | 役割の説明（例: 「データに基づき慎重に判断する」） |
| personality | str | 性格特性（例: 「論理的、冷静、批判的思考を重視」） |
| guidelines | str | 行動指針（例: 「必ずデータや根拠を示す。感情論は避ける」） |
| target_role | enum | any / proposer / judge（使用可能な役割） |
| created_at | datetime | 作成日時 |
| updated_at | datetime | 更新日時 |

#### プリセットの使い方

- **設定画面**で複数のプリセットを事前登録（CRUD操作）
- **ディベート設定画面**で各参加者（A/B/C）にプリセットをドロップダウンから割り当て
- プリセットの内容はLLMへのシステムプロンプトに組み込まれる
- 「プリセットなし（カスタム）」も選択可能（直接入力）

#### プリセット例

| プリセット名 | 性格 | 行動指針 | 対象 |
|---|---|---|---|
| データ重視の分析者 | 論理的、冷静、数値を好む | 必ず根拠を示す。感情論は排除 | 提案者向け |
| 情熱的な推進者 | 積極的、楽観的、ビジョン志向 | 将来の可能性を強調。具体例で説明 | 提案者向け |
| 厳格な批評家 | 懐疑的、公平、細部にこだわる | 両方の弱点を突く。矛盾を指摘 | 判定者向け |
| 実務家 | 現実的、コスト意識が高い | 実現可能性を重視。リスクを指摘 | どちらでも |
| 哲学者 | 思索的、多角的、本質を問う | 前提を疑う。根本的な問いを投げる | どちらでも |

### 3.2 ディベート（Debate）

| フィールド | 型 | 説明 |
|---|---|---|
| id | str (UUID) | ディベートID |
| title | str | ディベートタイトル |
| topic | str | 議論のテーマ |
| proposal_x | str | Aの主張テキスト（案X） |
| proposal_y | str | Bの主張テキスト（案Y） |
| judge_instruction | str | Cへの指示テキスト（判定の観点等） |
| status | enum | pending / running / paused / completed |
| max_rounds | int | 最大ラウンド数 |
| current_round | int | 現在のラウンド数 |
| winner | str | 判定結果（A / B / draw / undecided） |
| created_at | datetime | 作成日時 |
| completed_at | datetime | 完了日時 |

### 3.3 参加者（Participant）

| フィールド | 型 | 説明 |
|---|---|---|
| id | str (UUID) | 参加者ID |
| debate_id | str | 所属ディベートID |
| role | enum | proposer_a / proposer_b / judge |
| name | str | 表示名 |
| type | enum | human / llm |
| llm_provider | str | LLMプロバイダ名（LLM時） |
| llm_model | str | モデル名（LLM時） |
| preset_id | str (nullable) | 割り当てたロールプリセットID（nullならカスタム） |
| custom_role_desc | str (nullable) | カスタム役割説明（プリセット未使用時） |
| custom_personality | str (nullable) | カスタム性格（プリセット未使用時） |
| custom_guidelines | str (nullable) | カスタム行動指針（プリセット未使用時） |
| max_tokens_per_turn | int | 1回の発言最大トークン数 |
| include_own_thinking | bool | 自身の過去の思考をコンテキストに含めるか |

### 3.4 メッセージ（Message）

| フィールド | 型 | 説明 |
|---|---|---|
| id | str (UUID) | メッセージID |
| debate_id | str | ディベートID |
| participant_id | str | 発言者ID |
| round_number | int | ラウンド番号 |
| message_type | enum | speech / thinking / skip / judgment |
| content | str | メッセージ内容 |
| token_count | int | トークン数 |
| created_at | datetime | 作成日時 |

### 3.5 添付ファイル（Attachment）

主張（proposal_x, proposal_y, judge_instruction）に紐づく添付ファイル。
テキストでは伝えきれない情報（データ、図表、仕様書等）を補足するために使用する。

| フィールド | 型 | 説明 |
|---|---|---|
| id | str (UUID) | 添付ファイルID |
| debate_id | str | ディベートID |
| participant_role | enum | proposer_a / proposer_b / judge |
| original_filename | str | 元のファイル名 |
| stored_filename | str | 保存時のファイル名（UUID.ext） |
| file_type | enum | pdf / text / image / markdown / csv |
| file_size | int | ファイルサイズ（バイト） |
| extracted_text | str (nullable) | ファイルから抽出したテキスト内容 |
| created_at | datetime | 作成日時 |

#### 添付ファイルの扱い

- **保存先**: `data/attachments/{debate_id}/` にコピー保存
- **テキスト抽出**: PDF・テキスト・Markdown・CSVはテキスト抽出し `extracted_text` に保存
- **画像**: マルチモーダル対応LLMの場合はそのまま送信、非対応の場合はファイル名のみ記載
- **LLMへの送信**: 抽出テキストをシステムプロンプトの主張セクションに追記
- **対応形式**: `.pdf`, `.txt`, `.md`, `.csv`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`

### 3.6 SQLiteスキーマ

```sql
-- ロールプリセット
CREATE TABLE role_presets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role_description TEXT NOT NULL DEFAULT '',
    personality TEXT NOT NULL DEFAULT '',
    guidelines TEXT NOT NULL DEFAULT '',
    target_role TEXT NOT NULL DEFAULT 'any',  -- any / proposer / judge
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ディベート
CREATE TABLE debates (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    topic TEXT NOT NULL,
    proposal_x TEXT NOT NULL,
    proposal_y TEXT NOT NULL,
    judge_instruction TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    max_rounds INTEGER NOT NULL DEFAULT 5,
    current_round INTEGER NOT NULL DEFAULT 0,
    winner TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

-- 参加者
CREATE TABLE participants (
    id TEXT PRIMARY KEY,
    debate_id TEXT NOT NULL,
    role TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    llm_provider TEXT,
    llm_model TEXT,
    preset_id TEXT,
    custom_role_desc TEXT,
    custom_personality TEXT,
    custom_guidelines TEXT,
    max_tokens_per_turn INTEGER NOT NULL DEFAULT 500,
    include_own_thinking INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (debate_id) REFERENCES debates(id),
    FOREIGN KEY (preset_id) REFERENCES role_presets(id)
);

-- メッセージ
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    debate_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    message_type TEXT NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (debate_id) REFERENCES debates(id),
    FOREIGN KEY (participant_id) REFERENCES participants(id)
);

-- 添付ファイル
CREATE TABLE attachments (
    id TEXT PRIMARY KEY,
    debate_id TEXT NOT NULL,
    participant_role TEXT NOT NULL,  -- proposer_a / proposer_b / judge
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    file_type TEXT NOT NULL,        -- pdf / text / image / markdown / csv
    file_size INTEGER NOT NULL DEFAULT 0,
    extracted_text TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (debate_id) REFERENCES debates(id)
);

CREATE INDEX idx_messages_debate ON messages(debate_id, round_number);
CREATE INDEX idx_participants_debate ON participants(debate_id);
CREATE INDEX idx_attachments_debate ON attachments(debate_id, participant_role);
```

---

## 4. ディベート進行ロジック

### 4.1 進行フロー

```
[ディベート開始]
     │
     ▼
┌─────────────────────┐
│  ラウンド N 開始     │
│  (current_round++)  │
├─────────────────────┤
│                     │
│  1. A（提案者X）発言 │◄── LLM: API呼び出し / 人: テキスト入力待ち
│     ├─ 思考生成      │
│     └─ 発言生成      │
│                     │
│  2. B（提案者Y）発言 │◄── LLM: API呼び出し / 人: テキスト入力待ち
│     ├─ 思考生成      │
│     └─ 発言生成      │
│                     │
│  3. C（判定者）      │◄── LLM: API呼び出し / 人: 入力 or スキップ
│     ├─ 発言 or       │    (スキップ: ボタン or タイムアウト)
│     └─ スキップ      │
│                     │
└────────┬────────────┘
         │
         ▼
    ┌────────────┐     Yes
    │ 最大ラウンド ├────────► [Cが最終判定] → [完了]
    │ に到達？    │
    └────┬───────┘
         │ No
         ▼
    ┌────────────┐     Yes
    │ Cが判定を   ├────────► [完了]
    │ 宣言した？  │
    └────┬───────┘
         │ No
         ▼
    [次のラウンドへ戻る]
```

### 4.2 ターン管理の詳細

各ターンでの処理:

1. **現在の発言者を特定**（A → B → C の順）
2. **発言者がLLMの場合**:
   - プロンプトを構築（§4.3参照）
   - LLM APIを呼び出し（最大トークン制限付き）
   - 思考（thinking）と発言（speech）を分離して保存
   - 待ち時間は無制限（ローカルLLM対応）
3. **発言者が人間の場合**:
   - テキスト入力欄をアクティブ化
   - A/Bの場合: 入力待ち（無制限）
   - Cの場合: 入力待ち + スキップボタン + タイムアウト（デフォルト5秒、設定変更可能）
4. **発言を保存**（SQLiteに記録）
5. **UIを更新**（チャット画面に発言を追加）

### 4.3 LLMプロンプト構築ルール

LLMへのプロンプトは以下の要素で構成される:

```
[システムプロンプト]
  - ロールプリセット情報（性格・行動指針）※プリセット or カスタム入力
  - 役割説明（A: 案Xの推進者 / B: 案Yの推進者 / C: 中立の判定者）
  - 議論テーマと各提案の内容
  - 添付ファイルの抽出テキスト（存在する場合）
  - 発言ルール（1回の発言トークン上限の目安）

[会話履歴]
  - 全参加者の過去の「発言（speech）」を時系列で含める
  - 他者の「思考（thinking）」は含めない
  - 自身の「思考（thinking）」は設定（include_own_thinking）に応じて含める/含めない

[現在のターン指示]
  - "以下の形式で回答してください:"
  - "<thinking>ここにあなたの思考過程を記述</thinking>"
  - "<speech>ここに相手への発言を記述</speech>"
```

#### プロンプト構築例（Aのターン）

```
あなたは「案X」の推進者Aです。

【あなたの性格】{personality}  ※プリセットまたはカスタム入力から
【あなたの行動指針】{guidelines}  ※プリセットまたはカスタム入力から

【議論テーマ】{topic}

【あなたの主張（案X）】
{proposal_x}

{添付資料がある場合}
--- 参考資料（あなたの主張の根拠）---
{添付ファイルから抽出したテキスト}
--- 参考資料ここまで ---
{/添付資料がある場合}

【対立する主張（案Y）】{proposal_y}

あなたの目標は、判定者Cを説得して案Xが優れていると認めさせることです。
あなたの性格と行動指針に従って議論を展開してください。
1回の発言は簡潔にまとめてください。

--- 会話履歴 ---
{会話履歴: 全参加者のspeechのみ}
{自身のthinking: include_own_thinking=trueの場合のみ}
--- 会話履歴ここまで ---

以下の形式で回答してください:
<thinking>ここにあなたの思考過程を記述</thinking>
<speech>ここに発言を記述</speech>
```

### 4.4 Cのスキップ判定（LLMの場合）

CがLLMの場合、以下をプロンプトに追加:

```
あなたは判定者Cです。AとBの議論を聞いています。
今のラウンドで質問や意見がある場合は発言してください。
特になければ "<speech>SKIP</speech>" と回答してください。

十分に議論が尽くされ、判定を下せると判断した場合は:
<speech>
【判定】{A or B}の{案X or 案Y}を支持します。
【理由】{判定理由}
</speech>
と回答してください。
```

---

## 5. LLMプロバイダ統合

### 5.1 プロバイダ基底クラス

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        LLMにリクエストを送信し、レスポンスを返す。
        タイムアウトは設けない（ローカルLLM対応のため）。
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """接続設定の妥当性を検証する"""
        pass
```

### 5.2 対応プロバイダ一覧

| プロバイダ | 接続方式 | 主要モデル | 備考 |
|---|---|---|---|
| Azure OpenAI | REST API (azure-openai SDK) | GPT-4o, GPT-4, GPT-3.5 | エンドポイント+APIキー+デプロイ名 |
| Google Vertex AI | REST API (google-cloud-aiplatform) | Gemini Pro, Gemini Flash | プロジェクトID+リージョン+認証 |
| Anthropic | REST API (anthropic SDK) | Claude 3.5 Sonnet, Claude 3 Opus | APIキー |
| Ollama | ローカルHTTP (localhost:11434) | Llama 3, Mistral, etc. | 起動済みが前提 |
| LM Studio | ローカルHTTP (localhost:1234) | 任意のGGUFモデル | OpenAI互換API |
| Llama.cpp | ローカルHTTP (設定可能) | 任意のGGUFモデル | サーバーモード起動が前提 |

### 5.3 設定ファイル構成

#### `.env`（APIキー等の機密情報）

```env
# Azure OpenAI
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Anthropic
ANTHROPIC_API_KEY=your-key-here

# Google Vertex AI
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
VERTEX_AI_PROJECT_ID=your-project-id
VERTEX_AI_LOCATION=us-central1
```

#### `config/llm_providers.json`（モデル設定）

```json
{
  "providers": [
    {
      "id": "azure-gpt4o",
      "name": "Azure GPT-4o",
      "type": "azure_openai",
      "deployment_name": "gpt-4o",
      "api_version": "2024-08-01-preview",
      "default_max_tokens": 500,
      "default_temperature": 0.7
    },
    {
      "id": "anthropic-claude-sonnet",
      "name": "Claude 3.5 Sonnet",
      "type": "anthropic",
      "model": "claude-3-5-sonnet-20241022",
      "default_max_tokens": 500,
      "default_temperature": 0.7
    },
    {
      "id": "ollama-llama3",
      "name": "Ollama Llama 3",
      "type": "ollama",
      "model": "llama3",
      "base_url": "http://localhost:11434",
      "default_max_tokens": 500,
      "default_temperature": 0.7
    },
    {
      "id": "lmstudio-local",
      "name": "LM Studio (ローカル)",
      "type": "lmstudio",
      "base_url": "http://localhost:1234/v1",
      "default_max_tokens": 500,
      "default_temperature": 0.7
    },
    {
      "id": "llamacpp-local",
      "name": "Llama.cpp (ローカル)",
      "type": "llamacpp",
      "base_url": "http://localhost:8080",
      "default_max_tokens": 500,
      "default_temperature": 0.7
    }
  ]
}
```

#### `config/role_presets.json`（ロールプリセット初期データ）

```json
{
  "presets": [
    {
      "id": "preset-analyst",
      "name": "データ重視の分析者",
      "role_description": "データや数値に基づき、客観的な分析を行う",
      "personality": "論理的、冷静、数値を好む",
      "guidelines": "必ず根拠を示す。感情論は排除。定量的な比較を重視する。",
      "target_role": "proposer"
    },
    {
      "id": "preset-passionate",
      "name": "情熱的な推進者",
      "role_description": "ビジョンを掲げ、可能性を力強く訴える",
      "personality": "積極的、楽観的、ビジョン志向",
      "guidelines": "将来の可能性を強調。具体例で説明。聴衆の感情に訴えかける。",
      "target_role": "proposer"
    },
    {
      "id": "preset-critic",
      "name": "厳格な批評家",
      "role_description": "両方の主張を厳しく評価し、公正に判断する",
      "personality": "懐疑的、公平、細部にこだわる",
      "guidelines": "両方の弱点を突く。矛盾を指摘。根拠の強さで判断する。",
      "target_role": "judge"
    },
    {
      "id": "preset-pragmatist",
      "name": "実務家",
      "role_description": "実現可能性とコストを重視して現実的に評価する",
      "personality": "現実的、コスト意識が高い、実行力重視",
      "guidelines": "実現可能性を重視。リスクを指摘。具体的な実行計画を求める。",
      "target_role": "any"
    },
    {
      "id": "preset-philosopher",
      "name": "哲学者",
      "role_description": "本質的な問いを投げかけ、多角的に思考する",
      "personality": "思索的、多角的、本質を問う",
      "guidelines": "前提を疑う。根本的な問いを投げる。長期的・倫理的視点を重視。",
      "target_role": "any"
    }
  ]
}
```

---

## 6. UI設計

### 6.1 画面遷移

```
[メイン画面]
  ├── [新規ディベート設定画面] → [ディベート実行画面]
  ├── [履歴一覧画面] → [履歴詳細画面（思考表示可能）]
  ├── [ロールプリセット管理画面]
  └── [LLM設定画面]
```

### 6.2 新規ディベート設定画面（setup_view）

```
┌──────────────────────────────────────────────────────────────┐
│  新規ディベート設定                                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  テーマ: [____________________________________________]      │
│                                                              │
│  ┌─ 参加者A（案X推進）───────────────────────────────────┐   │
│  │ 担当: (●) LLM  ( ) 人間                              │   │
│  │ 名前: [___________]                                   │   │
│  │                                                       │   │
│  │ ロール: [データ重視の分析者      ▼] [カスタム入力に切替]  │   │
│  │  ※ プリセット選択時、性格・行動指針は読み取り専用で表示   │   │
│  │  性格:     論理的、冷静、数値を好む                     │   │
│  │  行動指針: 必ず根拠を示す。感情論は排除                  │   │
│  │                                                       │   │
│  │ 主張（案X）:                                           │   │
│  │ [テキスト入力エリア（複数行）                    ]      │   │
│  │ 添付ファイル: [ファイルを選択...] report.pdf (120KB) [×] │   │
│  │                                  data.csv (45KB)  [×]  │   │
│  │                                                       │   │
│  │ LLM:  [Azure GPT-4o        ▼]                         │   │
│  │ 最大トークン/回: [500___]                              │   │
│  │ □ 自身の過去の思考をコンテキストに含める                  │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─ 参加者B（案Y推進）───────────────────────────────────┐   │
│  │ 担当: (●) LLM  ( ) 人間                              │   │
│  │ 名前: [___________]                                   │   │
│  │                                                       │   │
│  │ ロール: [情熱的な推進者        ▼] [カスタム入力に切替]    │   │
│  │  性格:     積極的、楽観的、ビジョン志向                  │   │
│  │  行動指針: 将来の可能性を強調。具体例で説明              │   │
│  │                                                       │   │
│  │ 主張（案Y）:                                           │   │
│  │ [テキスト入力エリア（複数行）                    ]      │   │
│  │ 添付ファイル: [ファイルを選択...]                       │   │
│  │                                                       │   │
│  │ LLM:  [Claude 3.5 Sonnet   ▼]                         │   │
│  │ 最大トークン/回: [500___]                              │   │
│  │ □ 自身の過去の思考をコンテキストに含める                  │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─ 参加者C（判定者）────────────────────────────────────┐   │
│  │ 担当: ( ) LLM  (●) 人間                              │   │
│  │ 名前: [___________]                                   │   │
│  │                                                       │   │
│  │ ロール: [厳格な批評家          ▼] [カスタム入力に切替]    │   │
│  │  性格:     懐疑的、公平、細部にこだわる                  │   │
│  │  行動指針: 両方の弱点を突く。矛盾を指摘                  │   │
│  │                                                       │   │
│  │ 判定の観点・指示:                                       │   │
│  │ [テキスト入力エリア（複数行）                    ]      │   │
│  │ 添付ファイル: [ファイルを選択...]                       │   │
│  │                                                       │   │
│  │ LLM:  [―――――――――――――――――]（無効: 人間担当）             │   │
│  │ 最大トークン/回: [300___]                              │   │
│  │ □ 自身の過去の思考をコンテキストに含める                  │   │
│  │ スキップタイムアウト: [5__] 秒                          │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─ 進行設定 ────────────────────────────────────────────┐   │
│  │ 最大ラウンド数: [5___]                                 │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│              [キャンセル]     [ディベート開始]                  │
└──────────────────────────────────────────────────────────────┘
```

#### ロール選択の動作

- **プリセット選択時**: ドロップダウンからプリセットを選ぶと、性格・行動指針が読み取り専用で表示される
- **カスタム入力時**: 「カスタム入力に切替」をクリックすると、性格・行動指針が編集可能なテキストエリアに変わる
- プリセットのドロップダウンには `target_role` に応じたフィルタがかかる（A/Bには `proposer` + `any`、Cには `judge` + `any` を表示）

#### 添付ファイルの動作

- 「ファイルを選択...」ボタンでファイルダイアログを開く（複数選択可）
- 追加されたファイルはファイル名とサイズ付きでリスト表示
- 各ファイルの横に [×] ボタンで削除可能
- 対応形式: PDF, TXT, MD, CSV, PNG, JPG, JPEG, GIF, WEBP

### 6.3 ロールプリセット管理画面（preset_view）

```
┌──────────────────────────────────────────────────────────────┐
│  ロールプリセット管理                              [新規作成]  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─ プリセット一覧 ──────────────────────────────────────┐   │
│  │                                                       │   │
│  │  ● データ重視の分析者       [提案者向け]  [編集] [削除] │   │
│  │  ● 情熱的な推進者           [提案者向け]  [編集] [削除] │   │
│  │  ● 厳格な批評家             [判定者向け]  [編集] [削除] │   │
│  │  ● 実務家                   [どちらでも]  [編集] [削除] │   │
│  │  ● 哲学者                   [どちらでも]  [編集] [削除] │   │
│  │                                                       │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─ プリセット編集 ──────────────────────────────────────┐   │
│  │                                                       │   │
│  │ プリセット名: [データ重視の分析者_________]             │   │
│  │                                                       │   │
│  │ 対象ロール: (●) 提案者向け ( ) 判定者向け ( ) どちらでも │   │
│  │                                                       │   │
│  │ 役割の説明:                                            │   │
│  │ [データや数値に基づき、客観的な分析を行う     ]         │   │
│  │                                                       │   │
│  │ 性格:                                                  │   │
│  │ [論理的、冷静、数値を好む                     ]         │   │
│  │                                                       │   │
│  │ 行動指針:                                              │   │
│  │ [必ず根拠を示す。感情論は排除。定量的な比較を  ]         │   │
│  │ [重視する。反論には具体的なデータで応じる。     ]         │   │
│  │                                                       │   │
│  │              [キャンセル]     [保存]                     │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 6.4 ディベート実行画面（debate_view）

```
┌─────────────────────────────────────────────────────────────┐
│  テーマ: ○○ vs △△                  ラウンド: 2/5  [一時停止] [終了] │
├──────────────────────────────────────┬──────────────────────┤
│                                      │  参加者情報           │
│  ┌──────────────────────────────┐   │                      │
│  │ A (GPT-4o): 案Xについて...   │   │  A: GPT-4o           │
│  │              [ラウンド1]      │   │  役割: 案X推進        │
│  └──────────────────────────────┘   │  状態: 待機中         │
│                                      │                      │
│  ┌──────────────────────────────┐   │  B: Claude Sonnet    │
│  │ B (Claude): 案Yの利点は...   │   │  役割: 案Y推進        │
│  │              [ラウンド1]      │   │  状態: 発言中...      │
│  └──────────────────────────────┘   │                      │
│                                      │  C: あなた           │
│  ┌──────────────────────────────┐   │  役割: 判定者         │
│  │ C: (スキップ)                │   │  状態: 次のターン     │
│  │              [ラウンド1]      │   │                      │
│  └──────────────────────────────┘   ├──────────────────────┤
│                                      │  進行状況             │
│  ┌──────────────────────────────┐   │  ━━━━━━━━━━━━ 40%    │
│  │ A (GPT-4o): さらに案Xは...   │   │                      │
│  │              [ラウンド2]      │   │  残りラウンド: 3      │
│  └──────────────────────────────┘   │                      │
│                                      │                      │
│  ┌──────────────────────────────┐   │                      │
│  │ B (Claude): 発言生成中...     │   │                      │
│  │ ████████░░░░░                │   │                      │
│  └──────────────────────────────┘   │                      │
│                                      │                      │
├──────────────────────────────────────┴──────────────────────┤
│  ┌─ あなたの発言（Cのターン時のみアクティブ）─────────────────┐ │
│  │ [______________________________________]  [送信] [スキップ]│ │
│  │                           タイムアウト: 5秒  残り: 3秒    │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                               │
│  ※ Cのターン以外は入力欄は非アクティブ                          │
└───────────────────────────────────────────────────────────────┘
```

### 6.5 履歴詳細画面（観戦中は思考非表示、振り返り時は表示可能）

```
┌────────────────────────────────────────────────────────────┐
│  履歴: ○○ vs △△  (2024-01-15)         [Markdownエクスポート] │
├────────────────────────────────────────────────────────────┤
│  ☑ 思考（thinking）を表示する                               │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  --- ラウンド 1 ---                                        │
│                                                            │
│  ┌─ A (GPT-4o) ──────────────────────────────────┐        │
│  │ 💭 思考: Bの主張に対して、まずコスト面から...     │        │
│  │ 💬 発言: 案Xのメリットとして、まず...             │        │
│  └───────────────────────────────────────────────┘        │
│                                                            │
│  ┌─ B (Claude) ──────────────────────────────────┐        │
│  │ 💭 思考: Aはコスト面を強調しているが...          │        │
│  │ 💬 発言: 案Yは長期的な観点で...                  │        │
│  └───────────────────────────────────────────────┘        │
│                                                            │
│  ┌─ C (あなた) ──────────────────────────────────┐        │
│  │ 💬 発言: (スキップ)                             │        │
│  └───────────────────────────────────────────────┘        │
│                                                            │
│  --- ラウンド 2 ---                                        │
│  ...                                                       │
│                                                            │
│  === 最終判定 ===                                          │
│  判定者Cの結論: 案Xを支持                                   │
│  理由: ...                                                 │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 7. 思考と発言の分離管理

### 7.1 概念

```
LLMのレスポンス
├── thinking（思考）: LLMの内部推論。他の参加者には見えない
└── speech（発言）: 実際のディベートでの発言。全員に公開

保存時: 両方をmessagesテーブルに保存（message_typeで区別）
観戦時: speechのみ表示
振り返り時: thinking + speech の両方を表示可能
```

### 7.2 レスポンスパース

LLMのレスポンスから `<thinking>` と `<speech>` タグを抽出:

```python
def parse_llm_response(response: str) -> tuple[str, str]:
    """
    LLMレスポンスからthinkingとspeechを分離する。

    Returns:
        (thinking, speech) のタプル
    """
    thinking_match = re.search(r'<thinking>(.*?)</thinking>', response, re.DOTALL)
    speech_match = re.search(r'<speech>(.*?)</speech>', response, re.DOTALL)

    thinking = thinking_match.group(1).strip() if thinking_match else ""
    speech = speech_match.group(1).strip() if speech_match else response.strip()

    return thinking, speech
```

### 7.3 コンテキスト構築ルール

参加者Xのターンでコンテキストを構築する際:

| コンテキストに含む内容 | 条件 |
|---|---|
| 全参加者の過去の「発言（speech）」 | 常に含む |
| 他者の「思考（thinking）」 | **含めない** |
| 自身の過去の「思考（thinking）」 | `include_own_thinking` 設定に依存 |

---

## 8. Markdownエクスポート形式

### 8.1 出力例

```markdown
# ディベート: リモートワーク vs オフィスワーク

- **日時**: 2024-01-15 14:30
- **テーマ**: 新しい働き方の選択
- **案X**: リモートワーク中心の体制
- **案Y**: オフィスワーク中心の体制

## 参加者

| 役割 | 名前 | タイプ | モデル |
|---|---|---|---|
| A（案X推進） | Alice | LLM | GPT-4o |
| B（案Y推進） | Bob | LLM | Claude 3.5 Sonnet |
| C（判定者） | ユーザー | 人間 | - |

## ディベート内容

### ラウンド 1

#### A (Alice)
> **思考**: リモートワークの生産性データを用いて...
>
> **発言**: リモートワークは通勤時間の削減により...

#### B (Bob)
> **思考**: Aの生産性データには偏りがある可能性が...
>
> **発言**: オフィスワークにはチームの一体感という...

#### C (ユーザー)
*スキップ*

### ラウンド 2
...

## 最終判定

**結果**: 案X（リモートワーク）を支持
**理由**: ...

---
*LMDebate により生成*
```

---

## 9. 設定項目一覧

### 9.1 ディベート設定（各ディベート個別）

| 設定項目 | 型 | デフォルト | 説明 |
|---|---|---|---|
| max_rounds | int | 5 | 最大ラウンド数 |
| participant_a_type | enum | llm | Aの担当（llm / human） |
| participant_b_type | enum | llm | Bの担当（llm / human） |
| participant_c_type | enum | human | Cの担当（llm / human） |
| c_skip_timeout_sec | int | 5 | C（人間時）のスキップタイムアウト秒数 |

### 9.2 参加者個別設定

| 設定項目 | 型 | デフォルト | 説明 |
|---|---|---|---|
| llm_provider | str | - | 使用するLLMプロバイダID |
| preset_id | str | null | ロールプリセットID（nullならカスタム） |
| custom_role_desc | str | "" | カスタム役割説明 |
| custom_personality | str | "" | カスタム性格 |
| custom_guidelines | str | "" | カスタム行動指針 |
| max_tokens_per_turn | int | 500 | 1回の発言最大トークン数 |
| include_own_thinking | bool | true | 自身の過去思考をコンテキストに含めるか |

### 9.3 アプリケーション設定

| 設定項目 | 型 | デフォルト | 説明 |
|---|---|---|---|
| theme | str | dark | UIテーマ（dark / light） |
| language | str | ja | UI言語（ja） |
| export_dir | str | ./exports | Markdownエクスポート先 |
| db_path | str | ./data/debates.db | SQLiteファイルパス |
| attachments_dir | str | ./data/attachments | 添付ファイル保存先 |
| max_attachment_size_mb | int | 50 | 1ファイルの最大サイズ（MB） |
| max_attachments_per_participant | int | 5 | 参加者あたりの最大添付数 |

---

## 10. エラーハンドリング

### 10.1 LLM接続エラー

- API接続失敗時: エラーメッセージを表示し、リトライ/スキップを選択可能
- タイムアウト: ローカルLLM対応のため、デフォルトではタイムアウトなし（ユーザーが手動中断するまで待機）
- レスポンスパースエラー: `<thinking>/<speech>` タグがない場合、レスポンス全体をspeechとして扱う

### 10.2 データ保存エラー

- SQLite書き込み失敗時: エラーログ出力 + ユーザー通知
- ディベート途中のクラッシュ: 各メッセージは即座にDBに保存するため、再開時に途中から復旧可能

---

## 11. 非同期処理

### 11.1 方針

- LLM APIの呼び出しは非同期（`asyncio` + `threading`でTkinterと統合）
- UI操作はメインスレッドで実行
- LLM応答待ちの間、UIはブロックされない（ローディング表示）
- ディベートの一時停止/再開が可能

### 11.2 スレッド構成

```
メインスレッド（Tkinter UIループ）
  └── ワーカースレッド（LLM API呼び出し）
       ├── asyncio イベントループ
       └── 結果をキュー経由でメインスレッドに返す
```

---

## 12. 将来の拡張候補（MVP後）

以下はMVPには含めないが、将来検討する機能:

- ディベートテンプレート（よく使うテーマの保存）
- 複数ラウンド形式のバリエーション（自由形式、パネルディスカッション形式）
- LLMのストリーミング表示対応
- ディベートのリプレイ機能（タイムライン再生）
- 統計ダッシュボード（どのモデルが勝ちやすいか等）
- Web UI対応（Flask/FastAPI + React）
