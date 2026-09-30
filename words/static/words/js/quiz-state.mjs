export function createState(words) {
    return {queue: words, total: words.length, completed: 0, attempts: 0,
        firstCorrect: 0, seen: [], processed: [], feedback: null, pending: null,
        pendingCorrection: null, started: Date.now(), history: []};
}

export function applyGrade(state, submittedWord, result, requestId) {
    if (state.processed.includes(requestId)) return false;
    if (!state.queue.length || state.queue[0].id !== submittedWord.id) throw new Error('문제 순서가 변경되었습니다. 새로고침해주세요.');
    const first = !state.seen.includes(submittedWord.id);
    if (first) state.seen.push(submittedWord.id);
    if (first && result.is_correct) state.firstCorrect++;
    state.processed.push(requestId);
    state.attempts++;
    const word = {...state.queue.shift(), version: result.version};
    if (result.is_correct) state.completed++;
    else state.queue.push(word);
    state.feedback = {word, result, first};
    state.pending = null;
    state.history.push({word: word.word, correct: result.is_correct, attemptId: result.attempt_id});
    return true;
}

export function applyCorrection(state, result) {
    const feedback = state.feedback;
    if (!feedback || feedback.result.attempt_id !== result.attempt_id) throw new Error('변경할 문제를 찾지 못했습니다.');
    if (feedback.result.is_correct) return false;
    state.queue = state.queue.filter(word => word.id !== feedback.word.id);
    state.completed++;
    if (feedback.first) state.firstCorrect++;
    feedback.result = result;
    state.pendingCorrection = null;
    const record = state.history.find(item => item.attemptId === result.attempt_id);
    if (record) { record.correct = true; record.corrected = true; }
    return true;
}
