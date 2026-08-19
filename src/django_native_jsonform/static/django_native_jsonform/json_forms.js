(function () {
  "use strict";

  function directInput(node, attribute) {
    for (const child of node.children) {
      if (child.matches && child.matches(`input[${attribute}]`)) return child;
    }
    return null;
  }

  function markPresent(element) {
    let node = element.closest("[data-jsonform-node]");
    while (node) {
      const presence = directInput(node, "data-jsonform-presence");
      if (presence && !presence.disabled) presence.value = "True";
      node = node.parentElement && node.parentElement.closest("[data-jsonform-node]");
    }
  }

  function setEnabled(container, enabled) {
    container.querySelectorAll("input, select, textarea, button").forEach((input) => {
      if (input.hasAttribute("data-jsonform-permanent-disabled")) return;
      input.disabled = !enabled;
    });
  }

  function directChild(node, selector) {
    for (const child of node.children) {
      if (child.matches && child.matches(selector)) return child;
    }
    return null;
  }

  function switchUnion(select, markAsPresent = true) {
    const union = select.closest("[data-jsonform-union]");
    if (!union) return;
    if (markAsPresent) markPresent(select);
    const branches = directChild(union, ".jsonform-branches");
    if (!branches) return;
    Array.from(branches.children).forEach((branch) => {
      if (!branch.hasAttribute("data-jsonform-branch")) return;
      const branchValue = branch.dataset.jsonformBranchValue ?? branch.dataset.jsonformBranch;
      const selected = branchValue === String(select.value);
      branch.hidden = !selected;
      setEnabled(branch, selected && !select.disabled);
      if (selected && !select.disabled) {
        branch.querySelectorAll("[data-jsonform-selector]").forEach((nested) => {
          switchUnion(nested, false);
        });
      }
    });
  }

  function initialize(root) {
    root.querySelectorAll("[data-jsonform-selector]").forEach((selector) => {
      switchUnion(selector, false);
    });
  }

  function addArrayItem(button) {
    const array = button.closest("[data-jsonform-array]");
    const template = array.querySelector(":scope > template[data-jsonform-prototype]");
    const items = array.querySelector(":scope > [data-jsonform-items]");
    const count = directInput(array, "data-jsonform-count");
    if (!template || !items || !count) return;
    const index = Number.parseInt(count.value || "0", 10);
    const token = array.dataset.jsonformIndexToken;
    const wrapper = document.createElement("div");
    wrapper.innerHTML = template.innerHTML.split(token).join(String(index));
    const item = wrapper.firstElementChild;
    if (!item) return;
    setEnabled(item, true);
    initialize(item);
    items.appendChild(item);
    count.value = String(index + 1);
    markPresent(button);
  }

  function removeArrayItem(button) {
    const item = button.closest("[data-jsonform-item]");
    if (!item) return;
    const deletion = directInput(item, "data-jsonform-delete");
    if (deletion) {
      deletion.disabled = false;
      deletion.value = "True";
    }
    item.querySelectorAll("input, select, textarea").forEach((input) => {
      if (input !== deletion) input.disabled = true;
    });
    item.hidden = true;
  }

  function togglePresence(button) {
    const node = button.closest("[data-jsonform-node]");
    if (!node) return;
    const presence = directInput(node, "data-jsonform-presence");
    if (!presence) return;
    const enable = !["true", "1"].includes(String(presence.value).toLowerCase());
    presence.disabled = false;
    presence.value = enable ? "True" : "False";
    if (node.matches("fieldset")) {
      setEnabled(node, enable);
      presence.disabled = false;
      button.disabled = false;
      if (enable) {
        node.querySelectorAll("[data-jsonform-selector]").forEach((selector) => {
          switchUnion(selector, false);
        });
      }
    }
  }

  function handleChange(target) {
    if (!(target instanceof Element) || !target.closest("[data-jsonform-root]")) return;
    if (target.hasAttribute("data-jsonform-selector")) switchUnion(target);
    if (!target.hasAttribute("data-jsonform-presence") &&
        !target.hasAttribute("data-jsonform-count") &&
        !target.hasAttribute("data-jsonform-delete")) {
      markPresent(target);
    }
  }

  function bindJQueryChangeBridge(jQueryInstance) {
    if (!jQueryInstance || !jQueryInstance.fn) return;
    const selector = "[data-jsonform-root] [data-jsonform-selector]";
    const $document = jQueryInstance(document);
    $document.off("change.jsonForms", selector);
    $document.on("change.jsonForms", selector, function (event) {
      // A browser-generated change also reaches the native listener below.
      // Select2/Jet changes are synthetic and only reach this bridge.
      if (event.originalEvent) return;
      handleChange(this);
    });
  }

  function bindAdminChangeBridges() {
    const djangoJQuery = window.django && window.django.jQuery;
    const jetJQuery = window.jQuery;
    bindJQueryChangeBridge(djangoJQuery);
    if (jetJQuery !== djangoJQuery) bindJQueryChangeBridge(jetJQuery);
  }

  document.addEventListener("change", function (event) {
    handleChange(event.target);
  });

  document.addEventListener("input", function (event) {
    const target = event.target;
    if (target instanceof Element && target.closest("[data-jsonform-root]")) {
      markPresent(target);
    }
  });

  document.addEventListener("click", function (event) {
    const button = event.target.closest("button");
    if (!button || !button.closest("[data-jsonform-root]")) return;
    if (button.hasAttribute("data-jsonform-add")) addArrayItem(button);
    if (button.hasAttribute("data-jsonform-remove")) removeArrayItem(button);
    if (button.hasAttribute("data-jsonform-unset")) togglePresence(button);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initialize(document);
      bindAdminChangeBridges();
    });
  } else {
    initialize(document);
    bindAdminChangeBridges();
  }
})();
