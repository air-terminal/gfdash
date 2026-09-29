drop table IF EXISTS gf.tz391_llm_capability;

-- 推論エンジンと銘柄の組み合わせごとの能力
--
-- thinking の強さ(low/medium/high/max)は、推論エンジンと銘柄の組み合わせによって
-- 黙って無視される。Ollama は自身が解釈するが銘柄が非対応なら無視し、OpenAI互換の
-- reasoning_effort はチャットテンプレートに渡る変数にすぎないため、テンプレートが
-- 参照していなければ捨てられる。どちらもエラーにならず 200 が返るので、
-- リクエストの成否からは判定できない。
--
-- 唯一確実なのは実測で、temperature=0・同じ seed で強さを変えて投げ、出力が変わるかを見る。
-- 生成を伴うため画面のロードでは測れない。490 のボタンを押したときだけ測り、
-- 結果をこの表に残して次回以降の画面の出し分けに使う。
--
-- 併せて、そのとき使っていた実行パラメータも持つ。毎月同じ銘柄・同じ設定で運用する
-- ため、次回の画面で復元できると入力の手間と取り違えが減る。
create table gf.tz391_llm_capability (
    -- Django が単独主キーを要求するため id を持たせ、実際の一意性は
    -- (provider, endpoint, model_name) の UNIQUE で担保する（tz305 と同じ理由）
    id serial primary key,

    -- 'ollama' / 'openai'
    provider varchar(20) not null,

    -- 接続先(OLLAMA_API_URL / OPENAI_API_BASE)。
    --
    -- モデル名だけを鍵にしない。同じ銘柄でもサーバが違えば挙動が違う。
    -- 例えば harmony 形式を解釈するサーバでは強さが効くが、同じ銘柄を
    -- テンプレート任せのサーバで動かすと無視される。
    endpoint varchar(200) not null,

    model_name varchar(200) not null,

    -- 測定時のモデルのダイジェスト(Ollama のみ)。同名タグの中身が
    -- 入れ替わったことを検知して、再測定を促すために持つ
    model_digest varchar(80) not null default '',

    -- thinking 自体が使えるか
    think_supported boolean not null default false,

    -- 強さが効くか。真偽値にしないのは「未測定」と「測ったが分からなかった」を
    -- 区別するため。区別できないと、判定できないサーバで測定を繰り返させる。
    --   'unknown'       : 未測定
    --   'effective'     : 効く
    --   'ineffective'   : 効かない（黙って無視される）
    --   'indeterminate' : 判定不能。temperature=0 でも出力が毎回変わるサーバ。
    --                     連続バッチ処理やプレフィックスキャッシュで浮動小数点の
    --                     計算順序が変わるため起きる。サーバ側の起動条件でしか
    --                     改善できないので、状態として記録するだけにする
    effort_status varchar(20) not null default 'unknown',

    -- accepted になった強さの配列（例 '["low","medium","high"]'）。
    --
    -- エフェクト検証とは独立に決まる。400 か 200 かは計算のゆらぎに影響されないため、
    -- 判定不能なサーバでも「この値は送れない」は確定する
    effort_values jsonb not null default '[]'::jsonb,

    -- 判定の根拠。後から結果を疑えるように、比較した文字数などを残す
    probe_note text not null default '',

    -- ▼ 測定したときの実行パラメータ。能力とは独立に保存する（判定不能でも残す）
    --
    -- last_engine が違うときは復元しない。多段版と軽量版では num_ctx の
    -- 既定の意味が違う（多段版のまとめは thinking を使うので広い文脈が要る）
    last_engine varchar(20) not null default '',
    last_num_ctx integer,
    last_timeout integer,
    last_think boolean,
    last_effort varchar(10) not null default '',

    measured_at timestamptz,
    input_date date default current_date not null,

    constraint unique_llm_capability unique (provider, endpoint, model_name)
);
