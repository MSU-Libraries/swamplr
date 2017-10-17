# Swamplr

Swamplr is a modular set of tools primarily designed to interact with a Fedora Commons repository ([vers. 3.8](https://wiki.duraspace.org/display/FEDORA38/Fedora+3.8+Documentation)) as well as other components of the Fedora software stack ([Solr](https://lucene.apache.org/solr/guide/), [Gsearch](https://github.com/fcrepo3/gsearch), [Islandora](https://wiki.duraspace.org/display/ISLANDORA/Islandora), etc.)

## Available Apps

### Jobs (Core): swamplr_jobs
This is the core Swamplr app. Its purpose is to run and display results from jobs created by other apps. Part of its
design is to have a scheduled task that will run available jobs on a regular interval so that jobs can be scheduled to run
in advance. Job progress and other relevant information is displayed as each job runs, along with success or failure messages
on completion as applicable.

### Ingest: swamplr_ingest
An app designed to ingest new content into a Fedora Commons repository.

### Derivatives: swamplr_derivatives
An app that creates various derivatives for files that are to be ingested. The types of derivatives that are available to be generated are based on the type of content, for example images have options like creating a JPG, TIF and JP2. But audio objects have options to create waveforms preview images.  

### Services: swamplr_services
A more generic app that lets users create custom scripts that can be run on a scheduled interval. The user specifies the
command to run on the server and optionally the user to run it as (if not the same user that runs Swamplr).



#### Swamplr Ingest

```
# 'Compound' content models are those with hierarchical directory structures.
self.compound_content_models = ["compound", "newspaper_issue", "book"]
self.simple_content_models = ["large_image", "pdf", "newspaper_page", "oral_histories", "audio"]
```


**Hint Files**
