-- Deploy panels:add-panels-plugin to pg

BEGIN;

CREATE TABLE panel_applicant (
        id uuid NOT NULL,
        app_id uuid NOT NULL,
        submitter boolean DEFAULT false NOT NULL,
        first_name character varying DEFAULT ''::character varying NOT NULL,
        last_name character varying DEFAULT ''::character varying NOT NULL,
        email character varying DEFAULT ''::character varying NOT NULL,
        cellphone character varying DEFAULT ''::character varying NOT NULL
);

CREATE TABLE panel_application (
        id uuid NOT NULL,
        name character varying DEFAULT ''::character varying NOT NULL,
        length character varying DEFAULT ''::character varying NOT NULL,
        description character varying DEFAULT ''::character varying NOT NULL,
        unavailable character varying DEFAULT ''::character varying NOT NULL,
        affiliations character varying DEFAULT ''::character varying NOT NULL,
        past_attendance character varying DEFAULT ''::character varying NOT NULL,
        presentation integer NOT NULL,
        other_presentation character varying DEFAULT ''::character varying NOT NULL,
        tech_needs character varying DEFAULT ''::character varying NOT NULL,
        other_tech_needs character varying DEFAULT ''::character varying NOT NULL,
        applied timestamp without time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE panel_applicant
        ADD CONSTRAINT panel_applicant_pkey PRIMARY KEY (id);

ALTER TABLE panel_application
        ADD CONSTRAINT panel_application_pkey PRIMARY KEY (id);

ALTER TABLE panel_applicant
        ADD CONSTRAINT panel_applicant_app_id_fkey FOREIGN KEY (app_id) REFERENCES panel_application(id) ON DELETE CASCADE;

COMMIT;
