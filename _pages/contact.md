---
layout: page
permalink: /contact/
title: contact
description: Get in touch
nav: true
nav_order: 6
---

<div class="contact-form">
  <p>Feel free to reach out via the form below or connect with me on <a href="https://linkedin.com/in/marin-moran">LinkedIn</a> or <a href="https://github.com/msmfai">GitHub</a>.</p>

  <form action="https://formspree.io/f/maqpnoed" method="POST">
    <div class="form-group">
      <label for="name">Name</label>
      <input type="text" id="name" name="name" required>
    </div>

    <div class="form-group">
      <label for="email">Email</label>
      <input type="email" id="email" name="_replyto" required>
    </div>

    <div class="form-group">
      <label for="subject">Subject</label>
      <input type="text" id="subject" name="_subject" required>
    </div>

    <div class="form-group">
      <label for="message">Message</label>
      <textarea id="message" name="message" rows="6" required></textarea>
    </div>

    <input type="hidden" name="_next" value="https://msmfai.github.io/personal-site/contact/?success=true">

    <button type="submit" class="btn btn-primary">Send Message</button>
  </form>

  {% if page.url contains '?success=true' %}
  <div class="alert alert-success mt-4" role="alert">
    Thank you for your message! I'll get back to you soon.
  </div>
  {% endif %}
</div>

<style>
.contact-form {
  max-width: 600px;
  margin: 0 auto;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: var(--global-text-color);
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--global-divider-color);
  border-radius: 4px;
  background-color: var(--global-bg-color);
  color: var(--global-text-color);
  font-family: inherit;
  font-size: 1rem;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: var(--global-theme-color);
}

.btn-primary {
  background-color: var(--global-theme-color);
  color: white;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn-primary:hover {
  opacity: 0.9;
}
</style>
