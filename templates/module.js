
    lucide.createIcons();
    const rateRange = document.getElementById("rateRange");
    const rateValue = document.getElementById("rateValue");
    const rateInput = document.getElementById("rateInput");

    rateRange.addEventListener("input", function () {
        rateValue.textContent = rateRange.value;
        rateInput.value = rateRange.value;
    });
    let currentAudio = null;

    document.getElementById("playAudio").addEventListener("click", function () {
        const rate = parseInt(document.getElementById("rateRange").value);
        const urlParams = new URLSearchParams(window.location.search);
        const moduleId = parseInt(urlParams.get("module")) || 1;

        fetch('/generate_audio', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            module: moduleId,
            rate: rate,
        })
        })
        .then(response => response.json())
        .then(data => {
        if (currentAudio) {
            currentAudio.pause();
            currentAudio.currentTime = 0;
        }
        currentAudio = new Audio(data.audio);
        currentAudio.play();
        });
    });

    document.getElementById("stopAudio").addEventListener("click", function () {
        if (currentAudio) {
        currentAudio.pause();
        currentAudio.currentTime = 0; // reset audio
        }
    });

        let transcribedText = '';

        // Load and play reference audio
        fetch('/generate_audio')
        .then(response => response.json())
        .then(data => {
            document.getElementById('playAudio').onclick = () => {
            const audio = new Audio(data.audio);
            audio.play();
            };
        });

    function checkText(inputText) {
        fetch('/check_text', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            text: inputText,
            module: 1
        })
        })
        .then(response => response.json())
        .then(data => {
        const resultDiv = document.getElementById('result');
        const correctionDiv = document.getElementById('correctionContainer');
        correctionDiv.innerHTML = ''; // clear previous correction UI

        if (data.incorrect.length > 0) {
            let result = 'Incorrect words (yours / correct):<br>';
            data.incorrect.forEach(({ user, correct }, index) => {
            result += `'${user || ''}' should be '${correct || ''}'<br>`;
            });
            resultDiv.innerHTML = result;
            resultDiv.classList.add('text-red-500');
            resultDiv.classList.remove('text-green-500');

            // Create correction inputs
            data.incorrect.forEach(({ user, correct }) => {
                const wrapper = document.createElement('div');
                wrapper.className = "mb-2 flex items-center gap-2";

                const label = document.createElement('label');
                const syllables = splitWordForPronunciation(correct);
                const splitWord = syllables.join(" · ");
                label.textContent = "Enter correct word for: ";
                const wordWrapper = document.createElement("span");
                wordWrapper.className = "ml-1";

                const coloredSyllables = colorSyllables(syllables);
                coloredSyllables.forEach((syllable, idx) => {
                wordWrapper.appendChild(syllable);
                if (idx < syllables.length - 1) {
                    const dot = document.createElement("span");
                    dot.textContent = " · ";
                    dot.className = "text-gray-500";
                    wordWrapper.appendChild(dot);
            }
    });
    label.appendChild(wordWrapper);
    label.className = "font-medium text-gray-700";

    const input = document.createElement('input');
    input.type = 'text';
    input.className = "border rounded p-2 mt-1 flex-1";
    input.dataset.correct = correct;

    const feedback = document.createElement('span');
    feedback.className = "ml-2 font-semibold text-sm";

    // 🔍 Find pronunciation audio for this correct word
    const pronunciation = data.pronunciations.find(p => p.word === correct);
    const audio = pronunciation ? pronunciation.audio : null;

    const playBtn = document.createElement('button');
    playBtn.innerHTML = "🔊";
    playBtn.className = "text-blue-500 hover:text-blue-700 text-lg";
    playBtn.disabled = !audio;

    playBtn.onclick = () => {
        if (audio) {
        const audioElement = new Audio(audio);
        audioElement.play();
        }
    };

    input.addEventListener('input', () => {
        if (input.value.trim().toLowerCase() === correct.toLowerCase()) {
        feedback.textContent = "Okay ✅";
        feedback.classList.remove('text-red-500');
        feedback.classList.add('text-green-500');
        } else {
        feedback.textContent = "Re-enter ❌";
        feedback.classList.remove('text-green-500');
        feedback.classList.add('text-red-500');
        }
    });

    wrapper.appendChild(label);
    wrapper.appendChild(playBtn);
    wrapper.appendChild(input);
    wrapper.appendChild(feedback);
    correctionDiv.appendChild(wrapper);
    });

        } else {
            resultDiv.innerHTML = 'All words are correct!';
            resultDiv.classList.remove('text-red-500');
            resultDiv.classList.add('text-green-500');
        }
        });
    }

        // Submit typed text
        document.getElementById('submitTextButton').addEventListener('click', () => {
        const inputText = transcribedText || document.getElementById('userInput').value.trim();
        if (!inputText) {
            document.getElementById('result').innerHTML = 'Please type or upload something first.';
            return;
        }
        checkText(inputText);
        });

        // Submit uploaded audio
        finalTranscript = ""
        const button = document.getElementById('startBtn');
        
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            transcription.innerText = "Sorry, your browser doesn't support SpeechRecognition.";
            button.disabled = true;
        } else {
            const recognition = new SpeechRecognition();
            recognition.lang = 'en-US';
            recognition.interimResults = true; // Disable real-time display
            recognition.continuous = false;

            recognition.onstart = () => {
                button.innerText = "Listening...";
                transcription.innerText = "Listening...";
            };

            recognition.onresult = (event) => {
                finalTranscript = Array.from(event.results)
                .map(result => result[0].transcript)
                .join('');
            };

            recognition.onend = () => {
                button.innerText = "Start Listening";
                transcription.innerText = finalTranscript ? `You said: "${finalTranscript}"` : "Didn't catch that.";
            };

            recognition.onerror = (event) => {
                transcription.innerText = "Error: " + event.error;
            };

            button.onclick = () => {
                finalTranscript = "";
                recognition.start();
            };
        }
        document.getElementById('submitAudio').addEventListener('click', () => {
            checkText(finalTranscript)
        });
        
    //   });
        // Submit with Enter (no shift)
        document.getElementById('userInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            document.getElementById('submitTextButton').click();
        }
        });

        const referenceText = "{{ reference_text}}";
        const referenceWords = referenceText.split(" ");
        const referenceContainer = document.getElementById("referenceText");
        // Loop through each word and wrap it in a <span>
referenceWords.forEach(word => {
  const span = document.createElement("span");
  span.textContent = word + " "; // Keep spacing between words
  span.classList.add("hover-highlight"); // Add a class for styling
  referenceContainer.appendChild(span);
});

    function renderWords(highlightedWords = []) {
        referenceContainer.innerHTML = "";
        referenceWords.forEach((word, index) => {
            const span = document.createElement("span");
            span.className = "flex items-center space-x-1";

            const text = document.createElement("span");
            text.textContent = word;
            text.className = "font-semibold";

            span.appendChild(text);

            // Only add button if the word is in the incorrect list
            if (highlightedWords.includes(word)) {
                const btn = document.createElement("button");
                btn.innerHTML = "🔊";
                btn.className = "text-blue-500 hover:text-blue-700";
                btn.onclick = () => {
                    fetch(`/word_audio?word=${encodeURIComponent(word)}`)
                    .then(response => response.json())
                    .then(data => {
                        const audio = new Audio(data.audio);
                        audio.play();
                        audio.onended = () => {
                            renderWords([]); // Just show words without audio buttons after reading
                        };
                    });
                };
                span.appendChild(btn);
            }

            referenceContainer.appendChild(span);
        });
    }


    

    // Initial render with no audio buttons
    renderWords([]);
    function colorSyllables(syllables) {
    const colors = ["text-red-600", "text-blue-600", "text-green-600", "text-purple-600"];
    return syllables.map((syllable, i) => {
        const span = document.createElement('span');
        span.textContent = syllable;
        span.className = `${colors[i % colors.length]} font-bold`;
        return span;
    });
    }
    function splitWordForPronunciation(word) {
    return word
        .replace(/([aeiouy]+)/gi, '-$1')  // Insert - before vowels group
        .replace(/^-/, '')                // Remove dash at start if present
        .split('-');                      // Split into parts
    }
    
