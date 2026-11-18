BEGIN;
CREATE VIEW railone.correlated_settlement_evidence AS
SELECT e.evidence_id,e.utt_id,s.rtt_id FROM railone.settlement_evidence e
               JOIN railone.provider_submissions s ON s.utt_id=e.utt_id AND s.provider_id=e.provider_id
               LEFT JOIN railone.provider_callback_inbox c ON c.provider_id=e.provider_id
                    AND c.provider_event_id=e.callback_event_id AND c.signature_valid
               WHERE e.signed_evidence #>> '{payload,rtt_id}' = s.rtt_id
                 AND ((s.provider_id <> 'MPESA-KE' AND s.external_reference=e.provider_transaction_id)
                      OR (s.provider_id='MPESA-KE'
                          AND c.provider_event_id='MPESA-RESULT-' || s.external_reference
                          AND c.raw_payload->>'conversation_id'=s.external_reference
                          AND c.raw_payload->>'originator_conversation_id'=s.provider_context->>'originator_conversation_id'
                          AND c.raw_payload->>'transaction_id'=e.provider_transaction_id
                          AND c.raw_payload->'result_code'='0'::jsonb));

CREATE OR REPLACE FUNCTION railone.guard_rtt_operational_fence_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.rtt_id <> OLD.rtt_id OR NEW.utt_id <> OLD.utt_id
       OR NEW.fence_epoch <> OLD.fence_epoch
       OR NEW.request_sha256 <> OLD.request_sha256
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'RTT operational fence identity cannot change';
    END IF;
    IF OLD.state = 'RESERVED'
       AND NEW.state IN ('ACCEPTED_FOR_PROCESSING','REJECTED','UNKNOWN') THEN
        RETURN NEW;
    END IF;
    IF OLD.state IN ('RESERVED','ACCEPTED_FOR_PROCESSING','REJECTED','UNKNOWN')
       AND NEW.state = 'RELEASED_NO_EFFECT'
       AND EXISTS (
           SELECT 1 FROM railone.economic_fence_no_effect_evidence e
           WHERE e.utt_id = OLD.utt_id AND e.rtt_id = OLD.rtt_id
       ) THEN
        RETURN NEW;
    END IF;
    IF OLD.state IN ('RESERVED','ACCEPTED_FOR_PROCESSING','REJECTED','UNKNOWN')
       AND NEW.state = 'SETTLED'
       AND EXISTS (
           SELECT 1 FROM railone.correlated_settlement_evidence e
           WHERE e.utt_id = OLD.utt_id AND e.rtt_id = OLD.rtt_id
       ) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'unsafe RTT operational fence transition';
END;
$$;
COMMIT;
