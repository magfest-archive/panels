-- Verify panels:add-panels-plugin on pg

BEGIN;

SELECT * from panel_applicant;
SELECT * from panel_application;
SELECT * from assigned_panelist;
SELECT * from event;

ROLLBACK;
