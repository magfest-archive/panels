-- Revert panels:add-panels-plugin from pg

BEGIN;

DROP TABLE panel_applicant;

DROP TABLE panel_application;

DROP TABLE assigned_panelist;

DROP TABLE event;

COMMIT;
