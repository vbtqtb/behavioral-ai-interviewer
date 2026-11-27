"""Local chat page served at /test/<interview_id>. Adapted from the old Flask chat template.

The page holds the session and signature in memory, the same way the Qualtrics
embed does, and posts them to /next on every turn.
"""

import json

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Interview test</title>
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.1.0/jquery.min.js"></script>
</head>
<body>
    <div style="width: 95%; margin-left: auto; margin-right: auto; min-width: 300px; max-width: 800px; background-color: #fff; display: flex; flex-direction: column; padding: 1px; height: 700px;" class="chat-container">
        <div style="font-size: 14px; color: #555; padding: 6px 4px;">Test interview: __INTERVIEW_LABEL__</div>
        <div style="overflow-y: scroll; height: calc(100% - 220px); margin-bottom: 5px; border: 2px solid #ddd; border-radius: 5px; padding: 10px; display: flex; flex-direction: column; align-items: flex-end;" id="chatArea">&nbsp;</div>
        <div style="position: relative; margin-top: 5px;"><textarea style="width: 100%; resize: vertical; font-size: 18px; min-height: 150px; max-height: 150px; border: 2px solid #A9A9A9; border-radius: 10px; padding: 10px; overflow: auto; box-sizing: border-box;" placeholder="Type your message here..." maxlength="3000" id="inputBox"></textarea></div>
        <div style="display: flex; justify-content: flex-end; padding-top: 10px;">
            <div style="flex-grow: 1; font-size: 18px; border: none; height: 30px; line-height: 1.2; padding-left: 10px; color: rgb(53, 53, 53);">Please write full sentences.</div>
            <button style="background-color: #D3D3D3; color: black; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 18px; margin-right: 10px;" id="recordButton">Record response</button>
            <button style="background-color: #007AC0; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 18px;" id="submitButton">Submit response</button>
        </div>
    </div>
<script>
var interviewID = __INTERVIEW_JSON__;
var sessionID = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now());
var interviewSession = null;
var interviewSignature = null;

var chatArea = document.getElementById("chatArea");
var submitButton = document.getElementById("submitButton");
var userInput = document.getElementById("inputBox");
var recordButton = document.getElementById("recordButton");

function nextPayload(userMessage) {
    var payload = {
        user_message: userMessage,
        session_id: sessionID,
        interview_id: interviewID
    };
    if (interviewSession) {
        payload.session = interviewSession;
        payload.signature = interviewSignature;
    }
    return payload;
}

function remember(data) {
    if (data && data.session) interviewSession = data.session;
    if (data && data.signature) interviewSignature = data.signature;
}

function appendChatbotMessage(message, chatArea, status) {
    var messageContent = document.createElement("div");
    messageContent.style.cssText = "word-wrap: break-word; width: 80%; border: 1px solid #F6F6F6; border-radius: 5px; padding: 5px; margin-bottom: 10px; background-color: #F6F6F6; display: block; margin-right: auto; font-size: 18px; line-height: 1.5;";
    if (status === "waiting") {
        messageContent.innerHTML = '<div id="wave" style="position:relative; text-align:left;"><span class="dot" style="display:inline-block; width:12px; height:6px; border-radius:50%; margin-right:3px; background:#303131; animation: wave 1.3s linear infinite;"></span><span class="dot" style="display:inline-block; width:12px; height:6px; border-radius:50%; margin-right:3px; background:#303131; animation: wave 1.3s linear infinite; animation-delay: -1.1s;"></span><span class="dot" style="display:inline-block; width:12px; height:6px; border-radius:50%; margin-right:3px; background:#303131; animation: wave 1.3s linear infinite; animation-delay: -0.9s;"></span></div><style>@keyframes wave {0%, 60%, 100% {transform: initial;} 30% {transform: translateY(-7px);}}</style>';
        messageContent.id = "dancingDots";
    } else if (status === "response") {
        var existingDots = document.getElementById("dancingDots");
        if (existingDots) {
            existingDots.innerText = message.trim();
            existingDots.removeAttribute("id");
            chatArea.scrollTop = chatArea.scrollHeight;
            return;
        }
        messageContent.innerText = message.trim();
    }
    chatArea.appendChild(messageContent);
    chatArea.scrollTop = chatArea.scrollHeight;
}

function restoreInput() {
    submitButton.disabled = false;
    submitButton.style.backgroundColor = "#007BFF";
    submitButton.innerText = "Submit response";
    userInput.disabled = false;
    recordButton.disabled = false;
}

function showDagValidation(dagSvg, validationQuestion) {
    submitButton.disabled = true;
    submitButton.style.backgroundColor = "#ccc";
    userInput.disabled = true;
    recordButton.disabled = true;
    var existingDots = document.getElementById("dancingDots");
    if (existingDots) existingDots.remove();

    var dagContainer = document.createElement("div");
    dagContainer.style.cssText = "width: 90%; margin-bottom: 10px; margin-right: auto;";
    var svgBox = document.createElement("div");
    svgBox.style.cssText = "overflow-x: auto; border: 1px solid #d0d7e3; border-radius: 6px; padding: 8px; background: #f8faff; margin-bottom: 10px;";
    svgBox.innerHTML = dagSvg;
    dagContainer.appendChild(svgBox);
    var questionEl = document.createElement("div");
    questionEl.style.cssText = "font-size: 18px; line-height: 1.5; margin-bottom: 10px; color: #1e3a5f; font-weight: 500;";
    questionEl.innerText = validationQuestion;
    dagContainer.appendChild(questionEl);

    var btnRow = document.createElement("div");
    btnRow.style.cssText = "display: flex; gap: 10px; margin-bottom: 10px;";
    var yesBtn = document.createElement("button");
    yesBtn.innerText = "Yes";
    yesBtn.style.cssText = "padding: 8px 28px; font-size: 16px; background: #2563a8; color: white; border: none; border-radius: 5px; cursor: pointer;";
    var noBtn = document.createElement("button");
    noBtn.innerText = "No";
    noBtn.style.cssText = "padding: 8px 28px; font-size: 16px; background: #e5e7eb; color: #1e3a5f; border: none; border-radius: 5px; cursor: pointer;";
    btnRow.appendChild(yesBtn);
    btnRow.appendChild(noBtn);
    dagContainer.appendChild(btnRow);

    var correctionArea = document.createElement("div");
    correctionArea.style.display = "none";
    correctionArea.innerHTML = '<textarea id="dagCorrectionText" placeholder="Please briefly describe what is incorrect..." style="width:100%; height:80px; font-size:16px; border:1px solid #ccc; border-radius:5px; padding:6px; box-sizing:border-box;"></textarea><button id="dagCorrectionSubmit" style="margin-top:6px; padding:8px 20px; font-size:16px; background:#2563a8; color:white; border:none; border-radius:5px; cursor:pointer;">Submit</button>';
    dagContainer.appendChild(correctionArea);
    chatArea.appendChild(dagContainer);
    chatArea.scrollTop = chatArea.scrollHeight;

    yesBtn.addEventListener("click", function () {
        dagContainer.remove();
        sendDagFeedback("__DAG_ACCEPTED__", "Yes");
    });
    noBtn.addEventListener("click", function () {
        correctionArea.style.display = "block";
        yesBtn.disabled = true;
        noBtn.disabled = true;
    });
    correctionArea.querySelector("#dagCorrectionSubmit").addEventListener("click", function () {
        var correctionText = correctionArea.querySelector("#dagCorrectionText").value.trim();
        if (!correctionText) return;
        dagContainer.remove();
        sendDagFeedback("__DAG_REJECTED__::" + correctionText, "No – " + correctionText);
    });
}

function sendDagFeedback(sentinelMessage, displayLabel) {
    var userBubble = document.createElement("div");
    userBubble.style.cssText = "display: inline-block; max-width: 80%; border: 1px solid #ddd; border-radius: 5px; padding: 5px; margin-bottom: 10px; background-color: #ddd; word-wrap: break-word; font-size: 18px; line-height: 1.5;";
    userBubble.innerText = displayLabel;
    chatArea.appendChild(userBubble);
    appendChatbotMessage("", chatArea, "waiting");
    postNext(sentinelMessage);
}

function handleServerResponse(data) {
    remember(data);
    var nextQuestion = (data.message || "").trim();
    if (nextQuestion.indexOf("---END---") !== -1) {
        nextQuestion = nextQuestion.replace("---END---", "").trim();
        appendChatbotMessage(nextQuestion, chatArea, "response");
        submitButton.disabled = true;
        submitButton.innerText = "End of interview";
        userInput.disabled = true;
        recordButton.disabled = true;
        return;
    }
    if (data.dag_svg) {
        var existingDots = document.getElementById("dancingDots");
        if (existingDots) existingDots.remove();
        showDagValidation(data.dag_svg, nextQuestion);
    } else {
        appendChatbotMessage(nextQuestion, chatArea, "response");
        restoreInput();
    }
}

function postNext(userMessage) {
    jQuery.ajax({
        url: "/next",
        timeout: 60000,
        type: "POST",
        data: JSON.stringify(nextPayload(userMessage)),
        contentType: "application/json",
        dataType: "json",
        success: function (data) { handleServerResponse(data); },
        error: function (jqXHR, textStatus, errorThrown) {
            console.error("Error:", errorThrown, jqXHR.responseJSON || jqXHR.responseText);
            appendChatbotMessage("There was a technical error. Please try again.", chatArea, "response");
            restoreInput();
        }
    });
}

["copy", "cut", "paste"].forEach(function (eventType) {
    [chatArea, userInput].forEach(function (element) {
        element.addEventListener(eventType, function (event) { event.preventDefault(); });
    });
});

submitButton.addEventListener("click", function () {
    var userMessage = userInput.value.trim();
    if (!userMessage) return;
    userInput.value = "";
    submitButton.disabled = true;
    submitButton.style.backgroundColor = "#ccc";
    submitButton.innerText = "Waiting for reply...";
    recordButton.disabled = true;
    var messageContent = document.createElement("div");
    messageContent.style.cssText = "display: inline-block; max-width: 80%; border: 1px solid #ddd; border-radius: 5px; padding: 5px; margin-bottom: 10px; background-color: #ddd; word-wrap: break-word; white-space: pre-wrap; box-sizing: border-box; font-size: 18px; text-align: left; line-height: 1.5;";
    messageContent.innerText = userMessage;
    chatArea.appendChild(messageContent);
    appendChatbotMessage("", chatArea, "waiting");
    postNext(userMessage);
});

var mediaRecorder, audioChunks = [], stream;
recordButton.addEventListener("click", async function () {
    if (recordButton.textContent === "Record response") {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            recordButton.textContent = "Stop recording";
            submitButton.disabled = true;
            mediaRecorder.start();
            mediaRecorder.ondataavailable = function (event) { audioChunks.push(event.data); };
        } catch (err) {
            alert("Error accessing microphone: " + err.message);
            submitButton.disabled = false;
        }
    } else if (recordButton.textContent === "Stop recording") {
        recordButton.textContent = "Transcribing audio...";
        recordButton.disabled = true;
        mediaRecorder.stop();
        mediaRecorder.onstop = function () {
            var audioBlob = new Blob(audioChunks, { type: "audio/webm" });
            var reader = new FileReader();
            reader.onloadend = function () {
                var audioBase64 = reader.result.split(",")[1];
                jQuery.ajax({
                    url: "/transcribe",
                    type: "POST",
                    timeout: 60000,
                    data: JSON.stringify({ audio: audioBase64 }),
                    contentType: "application/json",
                    dataType: "json",
                    success: function (data) {
                        userInput.value = data.transcription || "Transcription failed. Please try again.";
                        recordButton.textContent = "Record response";
                        recordButton.disabled = false;
                        submitButton.disabled = false;
                    },
                    error: function (jqXHR, textStatus, errorThrown) {
                        console.error("Error:", errorThrown, jqXHR.responseJSON || jqXHR.responseText);
                        alert("Something went wrong with the transcription. Please try again.");
                        recordButton.textContent = "Record response";
                        recordButton.disabled = false;
                        submitButton.disabled = false;
                    }
                });
            };
            reader.readAsDataURL(audioBlob);
            stream.getTracks().forEach(function (track) { track.stop(); });
        };
    }
});

appendChatbotMessage("", chatArea, "waiting");
postNext("");
</script>
</body>
</html>
"""


def render_test_page(interview_id):
    """Return the test chat page with the interview id filled in."""
    safe = json.dumps(interview_id)
    label = (
        interview_id.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return _PAGE.replace("__INTERVIEW_JSON__", safe).replace("__INTERVIEW_LABEL__", label)
