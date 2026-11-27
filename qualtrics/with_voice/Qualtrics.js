Qualtrics.SurveyEngine.addOnload(function () {

	////////////////////////////////////////////////////////////////
	// SETTINGS — the only part you may need to edit
	////////////////////////////////////////////////////////////////
	// interview_id, interview_endpoint, and user_id normally come from
	// Qualtrics embedded data (set them in the survey flow). Uncomment a
	// line only to override that value.
	// var SETTINGS_INTERVIEW_ID = "HOMELESS_BERLIN";
	// var SETTINGS_ENDPOINT = "https://ai-interviewer.YOUR_SUBDOMAIN.workers.dev/";
	// var SETTINGS_USER_ID = "";

	// Add these embedded data fields in the survey flow so they are saved with
	// the response: interview_transcript, interview_dags, interview_done.
	// Very long interviews (over ~15,000 characters) are split: the main field
	// then says "SPLIT:N" and the text is in interview_transcript_1 ... _5
	// (same for interview_dags). Add those five fields too if your interviews
	// are long.

	var userID = (typeof SETTINGS_USER_ID !== "undefined" && SETTINGS_USER_ID) || Qualtrics.SurveyEngine.getEmbeddedData("user_id");
	var interviewID = (typeof SETTINGS_INTERVIEW_ID !== "undefined" && SETTINGS_INTERVIEW_ID) || Qualtrics.SurveyEngine.getEmbeddedData("interview_id");
	var endpoint = (typeof SETTINGS_ENDPOINT !== "undefined" && SETTINGS_ENDPOINT) || Qualtrics.SurveyEngine.getEmbeddedData("interview_endpoint");

	// Held in the browser for this page. Sent back with every turn.
	var interviewSession = null;
	var interviewSignature = null;

	// Qualtrics: each embedded data value must stay under 20KB (20,000 bytes).
	// https://www.qualtrics.com/support/survey-platform/survey-module/survey-flow/standard-elements/embedded-data/
	// Chunks are smaller than that so multibyte text still fits. Up to 5 chunks.
	var EMBEDDED_DATA_MAX_BYTES = 15000;
	var EMBEDDED_DATA_MAX_PARTS = 5;

	function writeEmbedded(name, value) {
		var text = String(value == null ? "" : value);
		var bytes = new TextEncoder().encode(text);
		var parts = [];
		var index = 0;
		while (index < bytes.length && parts.length < EMBEDDED_DATA_MAX_PARTS) {
			var end = Math.min(index + EMBEDDED_DATA_MAX_BYTES, bytes.length);
			while (end < bytes.length && (bytes[end] & 0xc0) === 0x80) end--;
			if (end <= index) end = Math.min(index + 1, bytes.length);
			parts.push(new TextDecoder().decode(bytes.slice(index, end)));
			index = end;
		}
		if (!parts.length) parts.push("");
		var truncated = index < bytes.length;
		if (parts.length === 1 && !truncated) {
			Qualtrics.SurveyEngine.setEmbeddedData(name, text);
			for (var clear = 1; clear <= EMBEDDED_DATA_MAX_PARTS; clear++) {
				Qualtrics.SurveyEngine.setEmbeddedData(name + "_" + clear, "");
			}
		} else {
			Qualtrics.SurveyEngine.setEmbeddedData(name, truncated ? "SPLIT:" + parts.length + ":TRUNCATED" : "SPLIT:" + parts.length);
			for (var n = 0; n < EMBEDDED_DATA_MAX_PARTS; n++) {
				Qualtrics.SurveyEngine.setEmbeddedData(name + "_" + (n + 1), parts[n] || "");
			}
		}
		if (truncated) console.error(name + " exceeded " + EMBEDDED_DATA_MAX_PARTS + " embedded-data chunks and was truncated.");
	}

	function remember(data) {
		if (!data) return;
		if (data.session) interviewSession = data.session;
		// The worker generates an id when user_id is empty; keep using it.
		if (data.session_id) userID = data.session_id;
		if (typeof data.signature === "string") interviewSignature = data.signature;
		var done = data.done === true || (typeof data.message === "string" && data.message.indexOf("---END---") !== -1);
		writeEmbedded("interview_transcript", data.transcript || "");
		writeEmbedded("interview_dags", JSON.stringify(data.dags || []));
		Qualtrics.SurveyEngine.setEmbeddedData("interview_done", done ? "1" : "0");
	}

	function nextBody(userMessage) {
		var payload = {
			user_message: userMessage,
			session_id: userID,
			interview_id: interviewID
		};
		if (interviewSession) {
			payload.session = interviewSession;
			payload.signature = interviewSignature;
		}
		return JSON.stringify({ route: "next", payload: payload });
	}

	var chatArea = document.getElementById("chatArea");
	var submitButton = document.getElementById("submitButton");
	var inputField = document.getElementById("inputBox");
	var recordButton = document.getElementById("recordButton");

	var mediaRecorder;
	var audioChunks = [];
	var stream;
	recordButton.addEventListener("click", async function () {
		if (recordButton.textContent === "Record response") {
			try {
				stream = await navigator.mediaDevices.getUserMedia({ audio: true });
				mediaRecorder = new MediaRecorder(stream);
				audioChunks = [];
				recordButton.textContent = "Stop recording";
				submitButton.disabled = true;
				mediaRecorder.start();
				mediaRecorder.ondataavailable = function (event) {
					audioChunks.push(event.data);
				};
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
						url: endpoint,
						type: "POST",
						timeout: 60000,
						data: JSON.stringify({ route: "transcribe", payload: { audio: audioBase64 } }),
						contentType: "application/json",
						dataType: "json",
						success: function (data) {
							inputField.value = data.transcription || "Transcription failed. Please try again.";
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

	function appendChatbotMessage(message, chatArea, status) {
		var messageContent = document.createElement("div");
		messageContent.style.cssText = "word-wrap: break-word; width: 80%; border: 1px solid #F6F6F6; border-radius: 5px; padding: 5px; margin-bottom: 10px; background-color: #F6F6F6; display: block; margin-right: auto; font-size: 18px; line-height: 1.5;";

		if (status === "waiting") {
			messageContent.innerHTML = `
            <div>
            <div id="wave" style="position:relative; vertical-align: center; text-align:left;">
            <span class="dot" style="display:inline-block; width:12px; height:6px; border-radius:50%; margin-right:3px; background:#303131; animation: wave 1.3s linear infinite;"></span>
            <span class="dot" style="display:inline-block; width:12px; height:6px; border-radius:50%; margin-right:3px; background:#303131; animation: wave 1.3s linear infinite; animation-delay: -1.1s;"></span>
            <span class="dot" style="display:inline-block; width:12px; height:6px; border-radius:50%; margin-right:3px; background:#303131; animation: wave 1.3s linear infinite; animation-delay: -0.9s;"></span>
            </div><style>@keyframes wave {0%, 60%, 100% {transform: initial;} 30% {transform: translateY(-7px);}}</style></div>`;
			messageContent.id = "dancingDots";
		} else if (status === "response") {
			var existingDots = document.getElementById("dancingDots");
			if (existingDots) {
				existingDots.innerText = message.trim();
				existingDots.removeAttribute("id");
				chatArea.scrollTop = chatArea.scrollHeight;
				return;
			} else {
				messageContent.innerText = message.trim();
			}
		}
		chatArea.appendChild(messageContent);
		chatArea.scrollTop = chatArea.scrollHeight;
	}

	function showDagValidation(dagSvg, validationQuestion) {
		submitButton.disabled = true;
		submitButton.style.backgroundColor = "#ccc";
		inputField.disabled = true;
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
		correctionArea.style.cssText = "display: none;";
		correctionArea.innerHTML = `
            <textarea id="dagCorrectionText" placeholder="Please briefly describe what is incorrect..."
                style="width:100%; height:80px; font-size:16px; border:1px solid #ccc; border-radius:5px; padding:6px; box-sizing:border-box; resize:vertical;"></textarea>
            <button id="dagCorrectionSubmit" style="margin-top:6px; padding:8px 20px; font-size:16px; background:#2563a8; color:white; border:none; border-radius:5px; cursor:pointer;">Submit</button>
        `;
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
			chatArea.scrollTop = chatArea.scrollHeight;
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
		chatArea.scrollTop = chatArea.scrollHeight;
		postNext(sentinelMessage);
	}

	function restoreInput() {
		submitButton.disabled = false;
		submitButton.style.backgroundColor = "#007BFF";
		submitButton.innerText = "Submit response";
		inputField.disabled = false;
		recordButton.disabled = false;
	}

	function handleServerResponse(data) {
		remember(data);
		var nextQuestion = (data.message || "").trim();

		if (nextQuestion.indexOf("---END---") !== -1) {
			nextQuestion = nextQuestion.replace("---END---", "").trim();
			appendChatbotMessage(nextQuestion, chatArea, "response");
			submitButton.disabled = true;
			submitButton.innerText = "End of interview";
			inputField.disabled = true;
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
			url: endpoint,
			timeout: 60000,
			type: "POST",
			data: nextBody(userMessage),
			contentType: "application/json",
			dataType: "json",
			success: function (data) {
				handleServerResponse(data);
			},
			error: function (jqXHR, textStatus, errorThrown) {
				console.error("Error:", errorThrown, jqXHR.responseJSON || jqXHR.responseText);
				appendChatbotMessage("There was a technical error. Please try again.", chatArea, "response");
				restoreInput();
			}
		});
	}

	jQuery.ajax({
		url: endpoint,
		timeout: 60000,
		type: "POST",
		data: nextBody(""),
		contentType: "application/json",
		dataType: "json",
		success: function (data) {
			var question = (data.message || "").trim();
			appendChatbotMessage(question, chatArea, "response");
			Qualtrics.SurveyEngine.setEmbeddedData("first_question", question);
			remember(data);
		},
		error: function (jqXHR, textStatus, errorThrown) {
			console.error("Error:", errorThrown, jqXHR.responseJSON || jqXHR.responseText);
			appendChatbotMessage("There was a technical error. Please refresh or proceed in the survey.", chatArea, "response");
		}
	});

	["copy", "cut", "paste"].forEach(function (eventType) {
		[chatArea, inputField].forEach(function (element) {
			element.addEventListener(eventType, function (event) {
				event.preventDefault();
			});
		});
	});

	submitButton.addEventListener("click", function () {
		var userMessage = inputField.value.trim();
		if (userMessage) {
			inputField.value = "";

			submitButton.disabled = true;
			submitButton.style.backgroundColor = "#ccc";
			submitButton.innerText = "Waiting for reply...";
			recordButton.disabled = true;

			var messageContent = document.createElement("div");
			messageContent.style.cssText = "display: inline-block; max-width: 80%; border: 1px solid #ddd; border-radius: 5px; padding: 5px; margin-bottom: 10px; background-color: #ddd; word-wrap: break-word; white-space: pre-wrap; box-sizing: border-box; font-size: 18px; text-align: left; line-height: 1.5;";
			messageContent.innerText = userMessage;
			chatArea.appendChild(messageContent);
			chatArea.scrollTop = chatArea.scrollHeight;

			appendChatbotMessage("", chatArea, "waiting");
			postNext(userMessage);
		}
	});

});

Qualtrics.SurveyEngine.addOnReady(function () {
});

Qualtrics.SurveyEngine.addOnUnload(function () {
});
