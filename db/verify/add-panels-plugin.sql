-- Verify panels:add-panels-plugin on pg

BEGIN;

SELECT * from panel_applicant;
SELECT * from panel_application;

ROLLBACK;
