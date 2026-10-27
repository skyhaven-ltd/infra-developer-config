(function () {
  "use strict";

  function store(key, value) {
    try {
      if (value === undefined) return JSON.parse(localStorage.getItem(key));
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      return null;
    }
  }

  function answerKeys(q) {
    return q.dataset.answer.split(",").map(function (s) { return s.trim(); }).sort();
  }

  function build(quiz) {
    var quizId = quiz.dataset.quizId || "quiz";
    var items = Array.prototype.slice.call(quiz.querySelectorAll(".q"));

    items.forEach(function (q, idx) {
      var answer = answerKeys(q);
      var multi = answer.length > 1;
      var name = quizId + "-" + (q.dataset.id || idx);
      var list = q.querySelector(".q-options");

      var head = document.createElement("div");
      head.className = "q-head";
      head.innerHTML = "<span>Question " + (idx + 1) + " of " + items.length + "</span>";
      var chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = q.dataset.domain;
      head.appendChild(chip);
      q.insertBefore(head, q.firstChild);

      var select = document.createElement("p");
      select.className = "q-select";
      select.textContent = multi ? "Select " + answer.length + "." : "Select 1.";
      list.parentNode.insertBefore(select, list);

      Array.prototype.forEach.call(list.children, function (li) {
        var key = li.dataset.key;
        var label = document.createElement("label");
        var input = document.createElement("input");
        input.type = multi ? "checkbox" : "radio";
        input.name = name;
        input.value = key;
        var k = document.createElement("span");
        k.className = "key";
        k.textContent = key + ".";
        var text = document.createElement("span");
        while (li.firstChild) text.appendChild(li.firstChild);
        label.appendChild(input);
        label.appendChild(k);
        label.appendChild(text);
        li.appendChild(label);
      });

      var verdict = document.createElement("p");
      verdict.className = "q-verdict";
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = "Check answer";
      button.disabled = true;
      var why = q.querySelector(".q-why");
      q.insertBefore(button, why);
      q.insertBefore(verdict, why);

      var inputs = Array.prototype.slice.call(q.querySelectorAll("input"));
      function picked() {
        return inputs.filter(function (i) { return i.checked; }).map(function (i) { return i.value; }).sort();
      }
      inputs.forEach(function (i) {
        i.addEventListener("change", function () {
          var n = picked().length;
          button.disabled = multi ? n !== answer.length : n !== 1;
        });
      });

      function reveal(choice) {
        var correct = choice.join(",") === answer.join(",");
        q.classList.add("done");
        q.dataset.result = correct ? "correct" : "wrong";
        inputs.forEach(function (i) {
          i.disabled = true;
          i.checked = choice.indexOf(i.value) !== -1;
          var label = i.parentNode;
          if (answer.indexOf(i.value) !== -1) label.classList.add("is-correct");
          else if (i.checked) label.classList.add("is-wrong");
        });
        button.hidden = true;
        verdict.textContent = correct ? "Correct" : "Not quite. Answer: " + answer.join(" and ");
        verdict.classList.add(correct ? "good" : "bad");
        summarise(quiz, items);
      }

      button.addEventListener("click", function () {
        var choice = picked();
        store("cca:" + quizId + ":" + name, choice);
        reveal(choice);
      });

      var saved = store("cca:" + quizId + ":" + name);
      if (Array.isArray(saved) && saved.length) reveal(saved);
    });

    summarise(quiz, items);
  }

  function summarise(quiz, items) {
    var box = quiz.querySelector(".quiz-summary");
    if (!box) return;
    var domains = {};
    var order = [];
    var done = 0;
    var right = 0;
    items.forEach(function (q) {
      var d = q.dataset.domain;
      if (!domains[d]) { domains[d] = { total: 0, done: 0, right: 0 }; order.push(d); }
      domains[d].total++;
      if (q.dataset.result) { domains[d].done++; done++; }
      if (q.dataset.result === "correct") { domains[d].right++; right++; }
    });
    order.sort();

    var rows = order.map(function (d) {
      var s = domains[d];
      return "<tr><td>" + d + "</td><td class=\"num\">" + s.right + " / " + s.total + "</td></tr>";
    }).join("");

    box.innerHTML =
      "<h3>Your results</h3>" +
      "<p class=\"total\">" + right + " correct of " + done + " answered (" + items.length + " total)</p>" +
      "<table><thead><tr><th>Domain</th><th class=\"num\">Correct</th></tr></thead><tbody>" + rows + "</tbody></table>" +
      "<div class=\"actions\"><button type=\"button\" data-act=\"copy\">Copy results for your teacher</button>" +
      "<button type=\"button\" data-act=\"reset\">Reset quiz</button></div>" +
      "<pre class=\"copy-fallback\" hidden></pre>";

    var text = (quiz.dataset.quizId || "quiz") + ": " + right + "/" + done + " answered of " + items.length + "\n" +
      order.map(function (d) { return d + ": " + domains[d].right + "/" + domains[d].total; }).join("\n") + "\n" +
      "Missed: " + items.filter(function (q) { return q.dataset.result === "wrong"; })
        .map(function (q, i) { return (q.dataset.id || i); }).join(", ");

    box.querySelector("[data-act=copy]").addEventListener("click", function (e) {
      var fallback = box.querySelector(".copy-fallback");
      function show() { fallback.textContent = text; fallback.hidden = false; }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () { e.target.textContent = "Copied"; }, show);
      } else {
        show();
      }
    });

    box.querySelector("[data-act=reset]").addEventListener("click", function () {
      var quizId = quiz.dataset.quizId || "quiz";
      items.forEach(function (q, idx) {
        store("cca:" + quizId + ":" + quizId + "-" + (q.dataset.id || idx), null);
      });
      location.reload();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    Array.prototype.forEach.call(document.querySelectorAll(".quiz"), build);
  });
})();
