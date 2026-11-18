BEGIN;
ALTER TABLE railone.economic_fence_events
    ADD COLUMN chain_position bigint,
    ADD COLUMN previous_hash bytea,
    ADD COLUMN event_hash bytea;

-- PostgreSQL binary record framing preserves field types, lengths, NULL and UTC instants.
CREATE FUNCTION railone.fence_event_hash(e railone.economic_fence_events) RETURNS bytea
LANGUAGE sql IMMUTABLE SET search_path = pg_catalog AS $$
    SELECT sha256(record_send(ROW('railone.fence.v1'::text, e.chain_position,
        e.previous_hash, e.event_number, e.utt_id, e.rtt_id, e.fence_epoch,
        e.event_type, e.evidence_id, e.recorded_at)))
$$;

-- ALTER TABLE holds an exclusive lock through backfill and trigger installation.
ALTER TABLE railone.economic_fence_events DISABLE TRIGGER economic_fence_events_immutable;
DO $$
DECLARE
    item railone.economic_fence_events;
    last_utt text;
    last_hash bytea;
    pos bigint;
BEGIN
    FOR item IN SELECT * FROM railone.economic_fence_events ORDER BY utt_id, event_number LOOP
        IF item.utt_id IS DISTINCT FROM last_utt THEN
            last_utt := item.utt_id;
            last_hash := decode(repeat('00',32),'hex');
            pos := 0;
        END IF;
        pos := pos + 1;
        item.previous_hash := last_hash;
        item.chain_position := pos;
        last_hash := railone.fence_event_hash(item);
        UPDATE railone.economic_fence_events SET chain_position=pos,
            previous_hash=item.previous_hash, event_hash=last_hash WHERE event_number=item.event_number;
    END LOOP;
END $$;
ALTER TABLE railone.economic_fence_events ENABLE TRIGGER economic_fence_events_immutable;
ALTER TABLE railone.economic_fence_events
    ALTER COLUMN chain_position SET NOT NULL,
    ALTER COLUMN previous_hash SET NOT NULL,
    ALTER COLUMN event_hash SET NOT NULL,
    ADD UNIQUE (utt_id, chain_position);

CREATE FUNCTION railone.link_fence_event() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.utt_id, 19));
    SELECT chain_position+1, event_hash INTO NEW.chain_position, NEW.previous_hash
        FROM railone.economic_fence_events WHERE utt_id=NEW.utt_id
        ORDER BY chain_position DESC LIMIT 1;
    IF NOT FOUND THEN
        NEW.chain_position := 1;
        NEW.previous_hash := decode(repeat('00',32),'hex');
    END IF;
    NEW.event_hash := railone.fence_event_hash(NEW);
    RETURN NEW;
END $$;
CREATE TRIGGER link_fence_event BEFORE INSERT ON railone.economic_fence_events
FOR EACH ROW EXECUTE FUNCTION railone.link_fence_event();

CREATE VIEW railone.fence_event_integrity AS
SELECT utt_id, chain_position, event_type, event_hash,
       chain_position = row_number() OVER stream
       AND previous_hash = lag(event_hash, 1, decode(repeat('00',32),'hex')) OVER stream
       AND event_hash = railone.fence_event_hash(e) AS valid
FROM railone.economic_fence_events e
WINDOW stream AS (PARTITION BY utt_id ORDER BY chain_position);
COMMIT;
