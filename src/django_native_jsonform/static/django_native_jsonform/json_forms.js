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

  const truthy = (input) => input && ["true", "1"].includes(String(input.value).toLowerCase());

  // Refresh top-down: enabling a parent must not enable a deleted item or an
  // inactive nested variant. Templates are inert and skipped until cloned.
  function refresh(element, enabled = true) {
    if (element.tagName === "TEMPLATE") return;
    let childEnabled = enabled;
    let presence = null;
    let deletion = null;
    if (element.hasAttribute("data-jsonform-node")) {
      presence = directInput(element, "data-jsonform-presence");
      if (element.tagName === "FIELDSET") {
        childEnabled = enabled && (element.dataset.jsonformRequired === "true" || truthy(presence));
      }
    }
    if (element.hasAttribute("data-jsonform-item")) {
      deletion = directInput(element, "data-jsonform-delete");
      element.hidden = truthy(deletion);
      childEnabled = enabled && !element.hidden;
    }
    if (element.hasAttribute("data-jsonform-branch")) {
      const union = element.closest("[data-jsonform-union]");
      const selector = union.querySelector("[data-jsonform-selector]");
      if (selector) element.hidden = (element.dataset.jsonformBranchValue ?? element.dataset.jsonformBranch) !== String(selector.value);
      childEnabled = enabled && !element.hidden;
    }
    if (element.matches("input, select, textarea, button")) {
      element.disabled = !enabled || element.hasAttribute("data-jsonform-permanent-disabled");
    }
    for (const child of element.children) {
      // Presence toggles and deletion markers remain submitted when their
      // own container is absent/deleted, but not when an ancestor is inactive.
      const ownControl = child === presence || child === deletion || child.hasAttribute("data-jsonform-unset");
      refresh(child, ownControl ? enabled : childEnabled);
    }
    if (element.hasAttribute("data-jsonform-array")) updateArrayLimits(element, childEnabled);
  }

  function updateArrayLimits(array, enabled) {
    const items = directChild(array, "[data-jsonform-items]");
    if (!items) return;
    const live = Array.from(items.children).filter((item) => !truthy(directInput(item, "data-jsonform-delete")));
    const minimum = Number(array.dataset.jsonformMinItems || 0);
    const maximum = array.dataset.jsonformMaxItems === "" ? Infinity : Number(array.dataset.jsonformMaxItems);
    const budget = Number(array.dataset.jsonformMaxRenderItems || 250);
    const add = directChild(array, "[data-jsonform-add]");
    if (add) add.disabled = !enabled || live.length >= maximum || live.length >= budget;
    live.forEach((item) => {
      const remove = directChild(item, ".jsonform-item-heading")?.querySelector("[data-jsonform-remove]");
      if (remove) remove.disabled = !enabled || live.length <= minimum;
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
    refresh(union.closest("[data-jsonform-root]"));
  }

  function initialize(root) {
    root.querySelectorAll("[data-jsonform-root]").forEach((form) => refresh(form));
  }

  function addArrayItem(button) {
    const array = button.closest("[data-jsonform-array]");
    const template = array.querySelector(":scope > template[data-jsonform-prototype]");
    const items = array.querySelector(":scope > [data-jsonform-items]");
    const count = directInput(array, "data-jsonform-count");
    if (!template || !items || !count) return;
    const deleted = Array.from(items.children).find((item) => truthy(directInput(item, "data-jsonform-delete")));
    const index = deleted ? Array.from(items.children).indexOf(deleted) : Number.parseInt(count.value || "0", 10);
    const token = array.dataset.jsonformIndexToken;
    const wrapper = document.createElement("div");
    wrapper.innerHTML = template.innerHTML.split(token).join(String(index));
    const item = wrapper.firstElementChild;
    if (!item) return;
    if (deleted) deleted.replaceWith(item);
    else {
      items.appendChild(item);
      count.value = String(index + 1);
    }
    markPresent(button);
    refresh(array.closest("[data-jsonform-root]"));
  }

  function removeArrayItem(button) {
    const item = button.closest("[data-jsonform-item]");
    if (!item) return;
    const deletion = directInput(item, "data-jsonform-delete");
    if (deletion) {
      deletion.disabled = false;
      deletion.value = "True";
    }
    refresh(item.closest("[data-jsonform-root]"));
  }

  function togglePresence(button) {
    const node = button.closest("[data-jsonform-node]");
    if (!node) return;
    const presence = directInput(node, "data-jsonform-presence");
    if (!presence) return;
    const enable = !["true", "1"].includes(String(presence.value).toLowerCase());
    presence.disabled = false;
    presence.value = enable ? "True" : "False";
    if (enable) markPresent(button);
    refresh(node.closest("[data-jsonform-root]"));
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
    if (!button || button.disabled || !button.closest("[data-jsonform-root]")) return;
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
