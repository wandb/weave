import random
import json
import pathlib

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import re
import pandas as pd
from tensorflow.keras.layers import TextVectorization


def load_data(dir_str):
    dir_path = pathlib.Path(dir_str)

    users = {}
    messages = []

    # Get all the channel names
    channel_names = sorted(
        d.name for d in dir_path.glob("*") if d.name in _ALLOWED_CHANNELS
    )

    # For each channel, get all the messages
    for channel_name in channel_names:
        files = (dir_path / channel_name).glob("*.json")
        for f in sorted(files):
            channel_messages = json.load(open(f))

            # For each message, parse the text and add the user if not already in the list
            for m in channel_messages:
                if m["type"] == "message" and "user_profile" in m:
                    text = _process_text(m["text"])
                    if text != "":
                        user_id = m["user"]
                        if user_id not in users:
                            users[user_id] = {
                                "user_id": user_id,
                                "count": 0,
                                "real_name": m["user_profile"]["real_name"],
                                "image_72": m["user_profile"]["image_72"],
                            }
                        users[user_id]["count"] += 1
                        messages.append([user_id, text])
    return {"users": users, "messages": messages}


def process_data(users, messages, min_msg_count=100, train_frac=0.8):
    # Strip out users with less than min_msg_count messages
    users = {k: v for k, v in users.items() if v["count"] >= min_msg_count}

    # Index the user ids
    user_ids = set(users.keys())
    for ndx, user_id in enumerate(user_ids):
        users[user_id]["model_id"] = ndx

    # Eliminate messages that are not in the top users & remap to index_id
    messages = [[users[m[0]]["model_id"], m[1]] for m in messages if m[0] in user_ids]

    # Split the training data
    n_train = int(len(messages) * train_frac)
    random.shuffle(messages)
    train_messages = messages[:n_train]
    test_messages = messages[n_train:]

    # Create the dataframes
    train_messages_df = pd.DataFrame(columns=["model_id", "text"], data=train_messages)
    test_messages_df = pd.DataFrame(columns=["model_id", "text"], data=test_messages)
    users_df = pd.DataFrame(data=users.values())

    return {
        "users": users_df,
        "train_messages": train_messages_df,
        "test_messages": test_messages_df,
    }


def make_baseline_model(data, vocab_size=20000, sequence_length=200):
    num_users = len(data["users"])
    raw_text = data["train_messages"]["text"].tolist()
    return _baseline_model(num_users, raw_text, vocab_size, sequence_length)


def make_transformer_model(
    data, vocab_size=20000, sequence_length=200, embed_dim=64, num_heads=6, ff_dim=64
):
    num_users = len(data["users"])
    raw_text = data["train_messages"]["text"].tolist()
    return _transformer_model(
        num_users, raw_text, vocab_size, sequence_length, embed_dim, num_heads, ff_dim
    )


def fit_model(model, data, batch_size=64, epochs=1):
    return model.fit(
        data["train_messages"]["text"].tolist(),
        data["train_messages"]["model_id"].tolist(),
        batch_size=batch_size,
        epochs=epochs,
        validation_data=(
            data["test_messages"]["text"].tolist(),
            data["test_messages"]["model_id"].tolist(),
        ),
    )


def package_model(model, data):
    inputs = tf.keras.Input(shape=(1,), dtype="string")
    indicies = tf.keras.layers.Reshape(target_shape=(1,))(
        _argmax_layer()(model(inputs))
    )

    ids = data["users"].sort_values("model_id")["model_id"].tolist()
    vocab = data["users"].sort_values("model_id")["real_name"].tolist()
    # layer = tf.keras.layers.StringLookup(vocabulary=vocab, invert=True)
    layer = _lookup_layer(ids, vocab)

    outputs = layer(indicies)

    # Our end to end model
    end_to_end_model = tf.keras.Model(inputs, outputs)
    end_to_end_model.compile(
        loss="binary_crossentropy", optimizer="adam", metrics=["accuracy"]
    )
    return end_to_end_model


##### Helpers #####
def _baseline_model(output_size, train_text, vocab_size=20000, sequence_length=200):
    inputs = layers.Input(shape=(1,), dtype=tf.string)
    x = _make_vectorizer(train_text, vocab_size, sequence_length)(inputs)
    x = layers.Dense(20, activation="relu")(x)  # was 20
    x = layers.Dropout(0.1)(x)
    outputs = layers.Dense(output_size, activation="softmax")(x)
    return keras.Model(inputs=inputs, outputs=outputs)


def _transformer_model(
    output_size,
    train_text,
    vocab_size=20000,
    sequence_length=200,
    embed_dim=64,  # Embedding size for each token
    num_heads=6,  # Number of attention heads
    ff_dim=64,  # Hidden layer size in feed forward network inside transformer
):
    inputs = layers.Input(shape=(1,), dtype=tf.string)
    x = _make_vectorizer(train_text, vocab_size, sequence_length)(inputs)
    embedding_layer = _TokenAndPositionEmbedding(sequence_length, vocab_size, embed_dim)
    x = embedding_layer(x)
    transformer_block = _TransformerBlock(embed_dim, num_heads, ff_dim)
    x = transformer_block(x)
    x = layers.GlobalAveragePooling1D()(x)
    x = layers.Dropout(0.1)(x)
    x = layers.Dense(20, activation="relu")(x)
    x = layers.Dropout(0.1)(x)
    outputs = layers.Dense(output_size, activation="softmax")(x)
    return keras.Model(inputs=inputs, outputs=outputs)


class _argmax_layer(tf.keras.layers.Layer):
    def __init__(self):
        super(_argmax_layer, self).__init__()

    def call(self, inputs):
        return tf.math.argmax(inputs, axis=1)


class _lookup_layer(tf.keras.layers.Layer):
    def __init__(self, keys, vals):
        super(_lookup_layer, self).__init__()
        keys_tensor = tf.constant(keys, dtype=tf.int64)
        vals_tensor = tf.constant(vals)
        init = tf.lookup.KeyValueTensorInitializer(
            keys_tensor, vals_tensor, value_dtype=tf.string
        )
        self.table = tf.lookup.StaticHashTable(init, default_value="")

    def call(self, inputs):
        return self.table.lookup(inputs)


class _TransformerBlock(layers.Layer):
    def __init__(self, embed_dim, num_heads, ff_dim, rate=0.1):
        super(_TransformerBlock, self).__init__()
        self.att = layers.MultiHeadAttention(num_heads=num_heads, key_dim=embed_dim)
        self.ffn = keras.Sequential(
            [
                layers.Dense(ff_dim, activation="relu"),
                layers.Dense(embed_dim),
            ]
        )
        self.layernorm1 = layers.LayerNormalization(epsilon=1e-6)
        self.layernorm2 = layers.LayerNormalization(epsilon=1e-6)
        self.dropout1 = layers.Dropout(rate)
        self.dropout2 = layers.Dropout(rate)

    def call(self, inputs, training):
        attn_output = self.att(inputs, inputs)
        attn_output = self.dropout1(attn_output, training=training)
        out1 = self.layernorm1(inputs + attn_output)
        ffn_output = self.ffn(out1)
        ffn_output = self.dropout2(ffn_output, training=training)
        return self.layernorm2(out1 + ffn_output)


class _TokenAndPositionEmbedding(layers.Layer):
    def __init__(self, maxlen, vocab_size, embed_dim):
        super(_TokenAndPositionEmbedding, self).__init__()
        self.token_emb = layers.Embedding(input_dim=vocab_size, output_dim=embed_dim)
        self.pos_emb = layers.Embedding(input_dim=maxlen, output_dim=embed_dim)

    def call(self, x):
        maxlen = tf.shape(x)[-1]
        positions = tf.range(start=0, limit=maxlen, delta=1)
        positions = self.pos_emb(positions)
        x = self.token_emb(x)
        return x + positions


def _custom_standardization(input_data):
    return tf.strings.lower(input_data)


def _make_vectorizer(train_text, vocab_size=20000, sequence_length=200):
    # Use the text vectorization layer to normalize, split, and map strings to
    # integers. Note that the layer uses the custom standardization defined above.
    # Set maximum_sequence length as all samples are not of the same length.
    vectorize_layer = TextVectorization(
        max_tokens=vocab_size, output_mode="int", output_sequence_length=sequence_length
    )

    vectorize_layer.adapt(train_text)

    return vectorize_layer


# # Vocabulary size and number of words in a sequence.
# vocab_size = 20000
# sequence_length = 200
# maxlen=200

# Make a text-only dataset (no labels) and call adapt to build the vocabulary.
# text_ds = train.map(lambda x, y: x)


def _process_text(text):
    # Remove special characters
    regex = r"\<([^\<^\>])*\>"
    text = re.sub(regex, "", text)

    # Remove Emojies
    regex = r":\w+:"
    text = re.sub(regex, " ", text)

    # Remove multiple spaces
    regex = r"\s+"
    text = re.sub(regex, " ", text)

    return text.strip()


_ALLOWED_CHANNELS = set(
    [
        "ab-testing",
        "accidental-art",
        "ae-cs-request",
        "ai-in-finance-april2022",
        "ama",
        "andreas",
        "animal-traffic-king",
        "anonymode",
        "api-design",
        "app-team",
        "app-team-dev",
        "artifacts",
        "astronomy",
        "attribution-data",
        "authors",
        "backlog-discussion",
        "baked-goods-i-made",
        "benchmarks",
        "best-sales-team",
        "bookclub",
        "carbon-track",
        "checkin-ganda",
        "checkin-growth",
        "checkin-gtm",
        "checkin-prodeng",
        "chicago_and_midwest",
        "china-community",
        "ci-improvements",
        "cloud-function-errors",
        "coffee",
        "community",
        "conf-anyscale-sf-2022",
        "conf-autoai-detroit-2022",
        "conf-cvpr-louisiana-2022",
        "conf-icml-baltimore-2022",
        "conf-mlops-summit-sf-2022",
        "conf-odsc-europe-2022",
        "conf-rev3-may2022",
        "content-ml-news",
        "content-requests",
        "content-sprint",
        "contract-review",
        "contributor-ian-kelk",
        "cooking",
        "core-flows",
        "course",
        "craiyon-fun-images",
        "cs-ama",
        "cs-hackathon-2022q1",
        "cs-hackathon-autonomous-driving",
        "cs-hackathon-healthcare",
        "cs-hackathon-retail",
        "cs-product",
        "cs-product-meeting-request",
        "custom-charts",
        "customers-info-collection-projectx",
        "cute-pix",
        "dagster",
        "data-checkins",
        "data-code-review",
        "data-tracker",
        "datalerts",
        "datalerts-mc-all",
        "datascience",
        "datascience-dev",
        "deletion-notices",
        "delivery-alerts-github",
        "delivery-alerts-managed-installs",
        "delivery-deployment-requests",
        "delivery-planning",
        "delivery-team",
        "demandgen",
        "deploy-alerts",
        "deploy-builds",
        "deployment-sessions",
        "deploys",
        "design",
        "devcontainers",
        "discord-admin",
        "discourse-bot",
        "discuss-1-wandb-org-per-company",
        "docs-and-examples",
        "dog-surfing-championship",
        "east-of-the-atlantic",
        "elden-ring",
        "emea-events",
        "emea-support-team",
        "emea_gtm",
        "eng",
        "eng-performance",
        "eng-projects",
        "eng-support-meetings",
        "enrichment",
        "enrichment-process",
        "enrichment-team",
        "enterprise-hackathon",
        "enterprise-levers",
        "example-dashboard-project",
        "examples-automation",
        "examples-repo-alerts",
        "examples-repo-revamp",
        "exec-sales-jail",
        "expansion-dev",
        "expansion-team",
        "expansion-team-planning",
        "explainer-videos",
        "fake-journal-club",
        "fc-admins",
        "feature-request-inbox",
        "featurebee",
        "financial-services-gtm",
        "foodies",
        "frontend-office-hours",
        "frontend-ui",
        "fullstory-bot",
        "fully-connected",
        "games",
        "gcp-commit-internal",
        "general",
        "geo-attribution",
        "global-sdr",
        "goals",
        "golf",
        "good-vibez",
        "gradient-dissent",
        "gratitude",
        "growth",
        "growth-3rd-party-integrations",
        "growth-alerts-testing",
        "growth-community-and-events",
        "growth-community-hf-swot",
        "growth-community-manager",
        "growth-community-support",
        "growth-content",
        "growth-events",
        "growth-games-mar16",
        "growth-gcp-alerts",
        "growth-ideas",
        "growth-jax-series",
        "growth-jonathan-whitaker",
        "growth-js-course",
        "growth-kaggle",
        "growth-kaggle-scraper",
        "growth-newsletter",
        "growth-referrals",
        "growth-sdrs",
        "growth-social-media",
        "growth-team",
        "growth-two-minute-papers-reports",
        "growth-updates",
        "growth-user-highlights",
        "growth-videos",
        "gtm",
        "hacking-application-data",
        "halp-bot",
        "hf-swot",
        "hf-swot-growth-content",
        "hf-swot-growth-product",
        "horns-and-hoofs",
        "i-want-prod-access",
        "industry-news",
        "infra-team",
        "infra-team-mysql-oom-p0",
        "integrations",
        "integrations-alerts",
        "integrations-repos",
        "intercom-bot",
        "it-support",
        "iterable",
        "iterable-integration",
        "janitor",
        "january-new-employees",
        "jeff-raubitschek",
        "jira",
        "justins-only",
        "kbd",
        "key-renewals-q222",
        "launch",
        "learned-league",
        "live-user-issues",
        "long-term-scaling",
        "marketing",
        "marketing-site",
        "mdli",
        "media",
        "memez",
        "ml",
        "ml-workflows-team",
        "mlw-triage",
        "model-registry",
        "multi-email",
        "nav-redesign",
        "navigation",
        "neurips-2021",
        "nlp",
        "nyc",
        "office",
        "office-music",
        "office-music-metalsucks",
        "partnerships",
        "partnerships-growth",
        "pendo-reviews",
        "pizza",
        "podcast-team",
        "product",
        "product-analytics",
        "product-and-product-marketing",
        "product-bots",
        "product-calls",
        "product-goals",
        "product-growth",
        "product-gtm",
        "product-launches",
        "product-metrics",
        "product-ml",
        "product-team",
        "product-updates",
        "productboard-users",
        "profile-page",
        "project-juno",
        "pseudorandom",
        "random",
        "reading-group",
        "recsys",
        "release-notes",
        "remote-international",
        "repo-insights",
        "reports",
        "retention",
        "revenue-data-streams",
        "revops-and-enablement",
        "runtime-reconciliation",
        "saas-system-requests",
        "sagemaker-integration",
        "sales-contract-review",
        "sales-marketing",
        "sales-product-leads",
        "sales-reps-only",
        "sales-request-cs",
        "sales-stories-and-demos-nominations",
        "sdk",
        "sdk-ci-nightly",
        "sdk-dev",
        "sdk-planning",
        "sdk-project-mp",
        "sdk-release-testing",
        "sdr-email-optimization",
        "sdr-support",
        "sdr-zendesk-bot",
        "se-hiring",
        "security",
        "security-team",
        "self-service",
        "sentry-anaconda2",
        "sentry-backend",
        "sf-office",
        "sko-2022-carpool",
        "sky-renewal-q1-2022",
        "snow-crew",
        "socal",
        "sre",
        "stackoverflow-questions",
        "starter-plan-edits",
        "stats-sim",
        "summerhack-analytics",
        "summerhack-launch",
        "summerhack22",
        "summerhack22-hotel",
        "sunsama-standups",
        "support-growth-sessions",
        "support-rotation",
        "support-team",
        "support-team-private",
        "swag",
        "swag-requests",
        "sweep_interviews",
        "sweeps",
        "sync-ml",
        "tables",
        "tables-growth-discussion",
        "tefoml-show",
        "temp-artifacts-team",
        "temp-make-pricing-page-better",
        "temp-qualtrics-model-reg",
        "timeseries",
        "tutorial-videos",
        "udacity",
        "view-only-seats",
        "waicf_customer_meetings",
        "wand_lgbtqia2s",
        "warriors",
        "wb-los-angeles",
        "wb101-first-projects",
        "wboxen",
        "weave",
        "weave-internal",
        "weave-product-link",
        "website-redesign",
        "welcome-igor",
        "window-to-the-world",
        "wnb-pytorch",
        "women-of-sillicon-valley-conference",
        "zendesk-bot",
    ]
)
