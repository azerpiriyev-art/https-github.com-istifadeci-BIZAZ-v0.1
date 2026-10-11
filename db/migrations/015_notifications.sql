BEGIN;

-- 015 BASIC NOTIFICATIONS
-- Additive tenant-scoped inbox; no existing business rows are rewritten.

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL
        REFERENCES companies(id) ON DELETE CASCADE,
    recipient_user_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    body VARCHAR(1000) NOT NULL,
    source_entity_type VARCHAR(50) NOT NULL,
    source_entity_id UUID NOT NULL,
    source_event_key VARCHAR(180) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at TIMESTAMPTZ NULL,

    CONSTRAINT fk_notifications_recipient_company_member
        FOREIGN KEY (recipient_user_id, company_id)
        REFERENCES company_members (user_id, company_id)
        ON DELETE CASCADE,

    CONSTRAINT uq_notifications_source_event_recipient
        UNIQUE (company_id, recipient_user_id, source_event_key),

    CONSTRAINT chk_notifications_event_type
        CHECK (event_type IN (
            'APPROVAL_ACTION_REQUIRED',
            'APPROVAL_DECISION_RECORDED',
            'PURCHASE_REQUEST_STATUS_CHANGED',
            'SUPPLIER_OFFER_SUBMITTED',
            'PURCHASE_ORDER_STATUS_CHANGED',
            'DELIVERY_STATUS_CHANGED',
            'PAYMENT_STATUS_CHANGED'
        )),

    CONSTRAINT chk_notifications_title_length
        CHECK (char_length(trim(title)) BETWEEN 1 AND 200),

    CONSTRAINT chk_notifications_body_length
        CHECK (char_length(trim(body)) BETWEEN 1 AND 1000)
);

CREATE INDEX idx_notifications_recipient_inbox
    ON notifications (company_id, recipient_user_id, created_at DESC, id DESC);

CREATE INDEX idx_notifications_recipient_unread
    ON notifications (company_id, recipient_user_id, created_at DESC, id DESC)
    WHERE read_at IS NULL;

COMMIT;
