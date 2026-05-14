---
layout: about
title: About
permalink: /
subtitle: Learning structure from unstructured data — physics, machine learning, and real-time systems

profile:
  align: right
  image: prof_pic.jpg
  image_circular: false # crops the image to make it circular
  more_info:

selected_papers: true # includes a list of papers marked as "selected={true}"
social: true # includes social icons at the bottom of the page

announcements:
  enabled: false # includes a list of news items
  scrollable: true # adds a vertical scroll bar if there are more than 3 news items
  limit: 5 # leave blank to include all the news in the `_news` folder

latest_posts:
  enabled: false
  scrollable: true # adds a vertical scroll bar if there are more than 3 new posts items
  limit: 3 # leave blank to include all the blog posts

timeline:
  enabled: true
  scrollable: true # adds a vertical scroll bar
  limit: # number of timeline items to show
---

I'm Marin. I build systems that extract structure from high-dimensional data with no canonical ordering. My work spans materials science (transformer architectures for periodic crystal graphs), real-time generative AI at Electronic Arts SEED, and scientific verification frameworks for frontier AI labs. The common thread is inference under uncertainty: learning what's invariant when the representation isn't canonical, and building systems robust enough to be trusted in production.

My PhD developed **Site-Net** — a transformer architecture for crystal structures, where the input is an infinite periodic graph with no canonical ordering — and established **Deep InfoMax** as a self-supervised methodology for domains where reconstruction is intractable. The same principle (extracting representations invariant to nuisance symmetries) underlies my production work at SEED, where I now apply it to latency-critical generative systems.

I have a long-running interest in market microstructure and complex systems — domains where these questions have immediate, measurable consequences.

{% if site.show_consultancy %}Separately, I run **Solomonoff Consultancy**, designing evaluation frameworks for scientific reasoning in frontier AI models — domains where ground truth is expensive to obtain and binary correctness is insufficient. Open to select engagements; get in touch to discuss fit.{% endif %}

## Research interests

Inference under uncertainty · invariant representations · information-theoretic learning · verification and evaluation design · real-time systems with hard latency budgets · market microstructure and complex systems.
