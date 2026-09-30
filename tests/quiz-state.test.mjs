import test from 'node:test';
import assert from 'node:assert/strict';
import {createState, applyGrade, applyCorrection} from '../words/static/words/js/quiz-state.mjs';
const words = () => [{id: 1, word: 'one', version: 0}, {id: 2, word: 'two', version: 0}];
test('duplicate responses cannot skip the next word', () => {
    const state = createState(words());
    const result = {is_correct: true, version: 1, attempt_id: 1};
    applyGrade(state, words()[0], result, 'request-1');
    assert.equal(applyGrade(state, words()[0], result, 'request-1'), false);
    assert.deepEqual(state.queue.map(w => w.id), [2]);
    assert.equal(state.completed, 1);
});
test('wrong answer is requeued with the new server version', () => {
    const state = createState(words());
    applyGrade(state, words()[0], {is_correct: false, version: 1, attempt_id: 1}, 'r');
    assert.deepEqual(state.queue.map(w => w.id), [2, 1]);
    assert.equal(state.queue[1].version, 1);
});
test('correction removes the matching word exactly once', () => {
    const state = createState(words());
    applyGrade(state, words()[0], {is_correct: false, version: 1, attempt_id: 1}, 'r');
    const corrected = {is_correct: true, version: 2, attempt_id: 1};
    applyCorrection(state, corrected);
    assert.equal(applyCorrection(state, corrected), false);
    assert.deepEqual(state.queue.map(w => w.id), [2]);
    assert.equal(state.completed, 1);
    assert.equal(state.firstCorrect, 1);
});
test('stale response cannot mutate a different question', () => {
    const state = createState(words());
    assert.throws(() => applyGrade(state, words()[1], {is_correct: true}, 'r'));
    assert.equal(state.queue.length, 2);
});
test('retry success is not counted as first-attempt success', () => {
    const state = createState([words()[0]]);
    applyGrade(state, words()[0], {is_correct: false, version: 1, attempt_id: 1}, 'a');
    state.feedback = null;
    applyGrade(state, state.queue[0], {is_correct: true, version: 2, attempt_id: 2}, 'b');
    assert.equal(state.attempts, 2);
    assert.equal(state.firstCorrect, 0);
    assert.equal(state.completed, state.total);
});
