"""Build the importable Qualtrics survey file from the HTML and JS in this folder.

Run after changing Qualtrics.html or Qualtrics.js:

    python3 qualtrics/build_qsf.py

It writes AI_Interviewer_Demo.qsf (text input) and AI_Interviewer_Demo_voice.qsf
(text and voice input). Researchers import one of them in Qualtrics and only
change interview_endpoint and interview_id in the survey flow.
"""

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Qualtrics IDs are a prefix plus 15 letters or digits. The importer assigns new ones.
SURVEY_ID = "SV_0AiInterview01"
RESPONSE_SET_ID = "RS_0AiInterview01"
OWNER_ID = "UR_0AiInterview01"
INTERVIEW_BLOCK = "BL_0AiInterview01"
END_BLOCK = "BL_0AiInterview02"
TRASH_BLOCK = "BL_0AiInterview03"
PLACEHOLDER_ENDPOINT = "https://ai-interviewer.YOUR-SUBDOMAIN.workers.dev/"

# Fields the player writes. Long interviews spill into _1 ... _5.
RESULT_FIELDS = (
    ["interview_transcript", "interview_dags", "interview_done", "first_question"]
    + [f"interview_transcript_{n}" for n in range(1, 6)]
    + [f"interview_dags_{n}" for n in range(1, 6)]
)


BLOCK_OPTIONS = {"BlockLocking": "false", "RandomizeQuestions": "false", "BlockVisibility": "Expanded"}


def element(kind, primary, payload, secondary=None, tertiary=None):
    return {
        "SurveyID": SURVEY_ID,
        "Element": kind,
        "PrimaryAttribute": primary,
        "SecondaryAttribute": secondary,
        "TertiaryAttribute": tertiary,
        "Payload": payload,
    }


def embedded(field, value=""):
    item = {
        "Description": field,
        "Type": "Custom",
        "Field": field,
        "VariableType": "String",
        "DataVisibility": [],
        "AnalyzeText": False,
    }
    if value:
        item["Value"] = value
    return item


def text_question(qid, tag, html, js=None):
    payload = {
        "QuestionText": html,
        "DefaultChoices": False,
        "DataExportTag": tag,
        "QuestionType": "DB",
        "Selector": "TB",
        "DataVisibility": {"Private": False, "Hidden": False},
        "Configuration": {"QuestionDescriptionOption": "UseText"},
        "QuestionDescription": tag,
        "ChoiceOrder": [],
        "Validation": {"Settings": {"Type": "None"}},
        "GradingData": [],
        "Language": [],
        "NextChoiceId": 4,
        "NextAnswerId": 1,
        "QuestionID": qid,
    }
    if js:
        payload["QuestionJS"] = js
    return {
        "SurveyID": SURVEY_ID,
        "Element": "SQ",
        "PrimaryAttribute": qid,
        "SecondaryAttribute": tag,
        "TertiaryAttribute": None,
        "Payload": payload,
    }


def build(variant, endpoint, interview_id, name):
    folder = HERE / variant
    html = (folder / "Qualtrics.html").read_text(encoding="utf-8")
    js = (folder / "Qualtrics.js").read_text(encoding="utf-8")

    flow = [
        {
            "Type": "EmbeddedData",
            "FlowID": "FL_2",
            "EmbeddedData": [
                embedded("user_id", "${e://Field/ResponseID}"),
                embedded("interview_id", interview_id),
                embedded("interview_endpoint", endpoint),
            ]
            + [embedded(field) for field in RESULT_FIELDS],
        },
        {"Type": "Block", "ID": INTERVIEW_BLOCK, "FlowID": "FL_3", "Autofill": []},
        {"Type": "Standard", "ID": END_BLOCK, "FlowID": "FL_4", "Autofill": []},
    ]

    elements = [
        {
            "SurveyID": SURVEY_ID,
            "Element": "BL",
            "PrimaryAttribute": "Survey Blocks",
            "SecondaryAttribute": None,
            "TertiaryAttribute": None,
            "Payload": [
                {
                    "Type": "Default",
                    "Description": "Interview",
                    "ID": INTERVIEW_BLOCK,
                    "BlockElements": [{"Type": "Question", "QuestionID": "QID1"}],
                    "Options": BLOCK_OPTIONS,
                },
                {
                    "Type": "Trash",
                    "Description": "Trash / Unused Questions",
                    "ID": TRASH_BLOCK,
                    "BlockElements": [],
                    "Options": BLOCK_OPTIONS,
                },
                {
                    "Type": "Standard",
                    "SubType": "",
                    "Description": "End",
                    "ID": END_BLOCK,
                    "BlockElements": [{"Type": "Question", "QuestionID": "QID2"}],
                },
            ],
        },
        {
            "SurveyID": SURVEY_ID,
            "Element": "FL",
            "PrimaryAttribute": "Survey Flow",
            "SecondaryAttribute": None,
            "TertiaryAttribute": None,
            "Payload": {
                "Type": "Root",
                "FlowID": "FL_1",
                "Flow": flow,
                "Properties": {"Count": 4},
            },
        },
        {
            "SurveyID": SURVEY_ID,
            "Element": "SO",
            "PrimaryAttribute": "Survey Options",
            "SecondaryAttribute": None,
            "TertiaryAttribute": None,
            "Payload": {
                "BackButton": "false",
                "SaveAndContinue": "true",
                "SurveyProtection": "PublicSurvey",
                "BallotBoxStuffingPrevention": "false",
                "NoIndex": "Yes",
                "SecureResponseFiles": "true",
                "SurveyExpiration": "None",
                "SurveyTermination": "DefaultMessage",
                "Header": "",
                "Footer": "",
                "ProgressBarDisplay": "None",
                "PartialData": "+1 week",
                "ValidationMessage": "",
                "PreviousButton": "",
                "NextButton": "",
                "SurveyTitle": name,
                "SkinLibrary": "",
                "SkinType": "MQ",
                "Skin": {"brandingId": None, "templateId": None, "overrides": None},
                "NewScoring": 1,
            },
        },
        element("PROJ", "CORE", {"ProjectCategory": "CORE", "SchemaVersion": "1.1.0"}, tertiary="1.1.0"),
        element("QC", "Survey Question Count", None, secondary="2"),
        element("RS", RESPONSE_SET_ID, None, secondary="Default Response Set"),
        element(
            "SCO",
            "Scoring",
            {
                "ScoringCategories": [],
                "ScoringCategoryGroups": [],
                "ScoringSummaryCategory": None,
                "ScoringSummaryAfterQuestions": 0,
                "ScoringSummaryAfterSurvey": 0,
                "DefaultScoringCategory": None,
                "AutoScoringCategory": None,
            },
        ),
        text_question("QID1", "interview", html, js),
        text_question(
            "QID2",
            "end",
            "Thank you. The interview is finished. Click the arrow to submit your answers.",
        ),
    ]

    return {
        "SurveyEntry": {
            "SurveyID": SURVEY_ID,
            "SurveyName": name,
            "SurveyDescription": None,
            "SurveyOwnerID": OWNER_ID,
            "SurveyBrandID": "aiinterviewer",
            "DivisionID": None,
            "SurveyLanguage": "EN",
            "SurveyActiveResponseSet": RESPONSE_SET_ID,
            "SurveyStatus": "Inactive",
            "SurveyStartDate": "0000-00-00 00:00:00",
            "SurveyExpirationDate": "0000-00-00 00:00:00",
            "SurveyCreationDate": "2026-11-18 00:00:00",
            "CreatorID": OWNER_ID,
            "LastModified": "2026-11-18 00:00:00",
            "LastAccessed": "0000-00-00 00:00:00",
            "LastActivated": "0000-00-00 00:00:00",
            "Deleted": None,
        },
        "SurveyElements": elements,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--endpoint", default=PLACEHOLDER_ENDPOINT)
    parser.add_argument("--interview-id", default="STOCK_MARKET")
    parser.add_argument("--out-dir", type=Path, default=HERE)
    args = parser.parse_args()

    for variant, filename, name in (
        ("without_voice", "AI_Interviewer_Demo.qsf", "AI Interviewer Demo"),
        ("with_voice", "AI_Interviewer_Demo_voice.qsf", "AI Interviewer Demo (voice)"),
    ):
        survey = build(variant, args.endpoint, args.interview_id, name)
        path = args.out_dir / filename
        path.write_text(json.dumps(survey, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()
