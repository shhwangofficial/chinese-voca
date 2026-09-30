(() => {
    const words = JSON.parse(document.getElementById('flash-data').textContent);
    if (!words.length) return;
    const $ = id => document.getElementById(`flash-${id}`);
    let index = 0;
    function render() {
        const word = words[index];
        $('count').textContent = `${index + 1} / ${words.length}`;
        $('word').textContent = word.word;
        $('answer').textContent = `${word.pinyin} ${word.tone}\n${word.meaning}\n${word.notes}`;
        $('answer').hidden = true;
        $('reveal').textContent = '답 보기';
        $('prev').disabled = index === 0;
        $('next').disabled = index === words.length - 1;
        $('error').textContent = '';
    }
    $('reveal').onclick = () => { $('answer').hidden = !$('answer').hidden; $('reveal').textContent = $('answer').hidden ? '답 보기' : '답 숨기기'; };
    $('prev').onclick = () => { if (index > 0) { index--; render(); } };
    $('next').onclick = () => { if (index < words.length - 1) { index++; render(); } };
    $('speak').onclick = () => {
        if (!('speechSynthesis' in window)) { $('error').textContent = '음성 재생을 지원하지 않는 브라우저입니다.'; return; }
        speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(words[index].word);
        utterance.lang = words[index].language === 'en' ? 'en-US' : 'zh-CN';
        utterance.onerror = () => { $('error').textContent = '해당 언어의 기기 음성을 사용할 수 없습니다.'; };
        speechSynthesis.speak(utterance);
    };
    document.addEventListener('keydown', event => {
        if (/INPUT|TEXTAREA|SELECT|BUTTON|A/.test(event.target.tagName)) return;
        if (event.key === 'ArrowLeft') { event.preventDefault(); $('prev').click(); }
        if (event.key === 'ArrowRight') { event.preventDefault(); $('next').click(); }
        if (event.key === ' ') { event.preventDefault(); $('reveal').click(); }
    });
    render();
})();
