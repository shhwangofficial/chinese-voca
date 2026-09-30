import {createState, applyGrade, applyCorrection} from './quiz-state.mjs';

const $ = id => document.getElementById(id);
const words = JSON.parse($('quiz-data').textContent);
const options = JSON.parse($('quiz-options').textContent);
const root = $('quiz-app');
const storageKey = `voca-quiz:${options.user_id}:${options.day}:${options.signature}`;
let state = createState(words);
let busy = false;
let saved;
try { saved = JSON.parse(sessionStorage.getItem(storageKey)); } catch { saved = null; }
if (saved && Array.isArray(saved.queue) && saved.queue.length && saved.started > Date.now() - 86400000) {
    $('resume-panel').hidden = false;
    $('resume').onclick = () => { state = saved; $('resume-panel').hidden = true; render(); };
    $('restart').onclick = () => { $('resume-panel').hidden = true; persist(); render(); };
}

function persist() {
    try { sessionStorage.setItem(storageKey, JSON.stringify(state)); }
    catch { $('storage-message').textContent = '이 브라우저에서는 이어하기를 저장할 수 없습니다.'; }
}
function error(message) { $('error').textContent = message; $('error').hidden = !message; }
function setBusy(value) {
    busy = value;
    for (const button of root.querySelectorAll('button')) button.disabled = value;
    for (const input of $('answer-form').querySelectorAll('input')) input.disabled = value || !!state.pending;
}
function uuid() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, c =>
        (Number(c) ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> Number(c) / 4).toString(16));
}
function currentWord() { return state.feedback ? state.feedback.word : state.queue[0]; }
function render() {
    error('');
    $('progress').value = state.completed;
    $('progress').max = state.total;
    $('progress-label').textContent = `${state.completed} / ${state.total}개 완료`;
    const done = !state.queue.length && !state.feedback;
    $('question').hidden = done;
    $('completion').hidden = !done;
    if (done) {
        $('summary').textContent = `${state.total}개 완료 · 첫 시도 정답률 ${Math.round(state.firstCorrect / state.total * 100)}% · 총 ${state.attempts}회 시도 · ${Math.max(1, Math.round((Date.now() - state.started) / 60000))}분`;
        $('history').replaceChildren(...state.history.map(item => {
            const li = document.createElement('li');
            li.textContent = `${item.word}: ${item.correct ? '정답' : '오답'}${item.corrected ? ' (정답 인정)' : ''}`;
            return li;
        }));
        try { sessionStorage.removeItem(storageKey); } catch { /* Optional storage. */ }
        return;
    }
    const word = currentWord();
    $('word').textContent = word.word;
    $('word-class').textContent = `${word.language === 'en' ? '영어' : '중국어'} · ${word.word_class}`;
    $('answer-form').hidden = !!state.feedback;
    $('feedback').hidden = !state.feedback;
    $('pinyin-fields').replaceChildren();
    const pending = state.pending?.data;
    if (word.language === 'zh') {
        const tones = word.tone.trim().split(/\s+/);
        for (let i = 0; i < Math.max(1, word.syllables); i++) {
            const label = document.createElement('label');
            label.className = 'syllable';
            label.append(document.createTextNode(`병음 ${i + 1}`));
            const input = document.createElement('input');
            input.name = `pinyin-${i}`;
            input.className = 'form-control pinyin-input';
            input.required = true; input.maxLength = 30;
            input.autocomplete = 'off'; input.autocapitalize = 'none'; input.spellcheck = false;
            input.value = pending?.pinyin?.split(' ')[i] || '';
            label.append(input);
            if (options.test_tone && word.tone) {
                const tone = document.createElement('input');
                tone.name = `tone-${i}`; tone.className = 'form-control tone-input';
                tone.setAttribute('aria-label', `${i + 1}번째 성조`);
                tone.inputMode = 'numeric'; tone.pattern = '[1-5]'; tone.maxLength = 1;
                tone.required = true; tone.placeholder = '성조 1~5';
                tone.value = pending?.tone?.split(' ')[i] || '';
                label.append(tone);
            } else {
                const help = document.createElement('small');
                help.textContent = `성조 ${tones[i] || '미등록'}`;
                label.append(help);
            }
            $('pinyin-fields').append(label);
        }
    }
    $('meaning').value = pending?.meaning || '';
    $('meaning').placeholder = `뜻 입력 (기준 답안 ${word.meaning_length}자, 추가 정답 허용)`;
    $('submit').textContent = pending ? '같은 답안 다시 전송' : '정답 확인';
    if (state.feedback) {
        const result = state.feedback.result;
        $('result-title').textContent = result.is_correct ? `정답! ${result.next_review_delta}일 뒤 복습합니다.` : '오답입니다. 잠시 후 다시 출제됩니다.';
        $('correct-answer').textContent = `${result.correct_pinyin || ''} ${result.word_tone || ''} · ${result.correct_meaning}`;
        $('mark-correct').hidden = result.is_correct;
        $('next').textContent = state.queue.length ? '다음 문제' : '결과 보기';
    }
    setBusy(false);
    if (state.pendingCorrection) $('next').disabled = true;
    const focusTarget = state.feedback ? $('next') : ($('pinyin-fields').querySelector('input') || $('meaning'));
    focusTarget.focus();
}
async function post(url, data) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
        const response = await fetch(url, {method: 'POST', signal: controller.signal,
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': $('csrf-form').querySelector('input').value},
            body: JSON.stringify(data)});
        if (response.status === 401) throw new Error('로그인이 만료됐습니다. 새 탭에서 로그인 후 같은 답안을 다시 전송하세요.');
        if (response.status === 403) throw new Error('보안 토큰이 만료됐습니다. 새로고침 후 이어하기를 선택하세요.');
        const result = await response.json();
        if (!response.ok || result.status !== 'success') throw new Error(result.message || '저장하지 못했습니다. 다시 시도해주세요.');
        return result;
    } catch (e) {
        if (e.name === 'AbortError') throw new Error('응답 시간이 초과됐습니다. 같은 답안을 다시 전송해도 중복 저장되지 않습니다.');
        throw e;
    } finally { clearTimeout(timeout); }
}
$('answer-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || state.feedback) return;
    if (!state.pending) {
        const word = state.queue[0];
        state.pending = {word, data: {request_id: uuid(), word_id: word.id, version: word.version,
            pinyin: [...root.querySelectorAll('.pinyin-input')].map(i => i.value.trim()).join(' '),
            tone: [...root.querySelectorAll('.tone-input')].map(i => i.value.trim()).join(' '),
            test_tone: options.test_tone && !!word.tone, meaning: $('meaning').value.trim()}};
        persist();
    }
    setBusy(true); error('');
    try {
        const {word, data} = state.pending;
        const result = await post(root.dataset.gradeUrl, data);
        applyGrade(state, word, result, data.request_id);
        persist(); render();
    } catch (e) {
        render(); error(e.message || '통신 오류입니다. 같은 답안을 다시 전송해주세요.');
    } finally { setBusy(false); }
});
$('next').onclick = () => {
    if (busy || state.pendingCorrection) return;
    state.feedback = null; persist(); render();
};
$('mark-correct').onclick = async () => {
    if (busy || !state.feedback || state.feedback.result.is_correct) return;
    state.pendingCorrection = state.feedback.result.attempt_id; persist();
    setBusy(true); error('');
    try {
        const result = await post(root.dataset.correctUrl, {attempt_id: state.pendingCorrection});
        applyCorrection(state, result); persist(); render();
    } catch (e) { error(e.message || '정답 인정에 실패했습니다. 다시 시도해주세요.'); }
    finally { setBusy(false); if (state.pendingCorrection) $('next').disabled = true; }
};
$('speak').onclick = () => {
    if (!('speechSynthesis' in window)) { error('이 브라우저는 음성 재생을 지원하지 않습니다.'); return; }
    speechSynthesis.cancel();
    const word = currentWord();
    const utterance = new SpeechSynthesisUtterance(word.word);
    utterance.lang = word.language === 'en' ? 'en-US' : 'zh-CN';
    utterance.rate = Number($('speech-rate').value);
    utterance.onerror = () => error('해당 언어의 음성을 재생할 수 없습니다. 기기 음성 설정을 확인해주세요.');
    speechSynthesis.speak(utterance);
};
window.addEventListener('beforeunload', () => { if (state.queue.length || state.feedback) persist(); });
render();
