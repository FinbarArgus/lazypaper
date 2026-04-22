-- Lazypaper: store of articles already emailed (one row per recipient + article_id).
-- Run once in Neon’s SQL editor (or any PostgreSQL client).
--
-- user_key: stores RECIPIENT_EMAIL from config.py (one namespace per recipient; many users can share one DB).

CREATE TABLE IF NOT EXISTS sent_article (
    user_key   TEXT        NOT NULL,
    article_id TEXT        NOT NULL,
    sent_at    DATE        NOT NULL,
    title      TEXT        NOT NULL DEFAULT '',
    journal    TEXT        NOT NULL DEFAULT '',
    PRIMARY KEY (user_key, article_id)
);

CREATE INDEX IF NOT EXISTS idx_sent_article_user_key ON sent_article (user_key);
