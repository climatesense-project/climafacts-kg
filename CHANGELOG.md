# CHANGELOG

<!-- version list -->

## v2.5.0 (2026-10-05)

### Bug Fixes

- **builders**: Sanitize control characters in literals and validate RDF/XML output
  ([`205eadb`](https://github.com/climatesense-project/climafacts-kg/commit/205eadb90128cba81c587fd94585fd779f6a2b24))

### Continuous Integration

- **release**: Separate software and data release workflows
  ([`6d79379`](https://github.com/climatesense-project/climafacts-kg/commit/6d793792b39494253d3f334d4f12a85e6ca7fbc5))

### Documentation

- Correct the graph cost estimates with a measured gate share and glm cost
  ([`3aa67d1`](https://github.com/climatesense-project/climafacts-kg/commit/3aa67d1272582b3d35797cb7812822c06da743cd))

- Streamline documentation, add CARDS taxonomy and SPARQL guides
  ([`5ecbdd9`](https://github.com/climatesense-project/climafacts-kg/commit/5ecbdd9343eb9ec17c2b9f5c592e8f4691fae062))

### Features

- **classifiers**: Add the gemma-tuned preset
  ([`a0975a9`](https://github.com/climatesense-project/climafacts-kg/commit/a0975a959dca6648f6e6f0cc9993929d667d6562))

- **eval**: Let the prompt optimizer target the balanced score
  ([`c66f794`](https://github.com/climatesense-project/climafacts-kg/commit/c66f794babf031fc34ecf3faa8d67dd9e294b519))


## v2.4.1 (2026-10-04)

### Bug Fixes

- **builders**: Sanitize control characters in literals and validate RDF/XML output
  ([`6fd9835`](https://github.com/climatesense-project/climafacts-kg/commit/6fd9835cbef97ec43bbc320cde6077c5dc48ab26))

### Documentation

- Cut the README's evaluation section to a pointer
  ([`e4082af`](https://github.com/climatesense-project/climafacts-kg/commit/e4082af889891cc561062bfc1073fa4237d3535b))

- Drop the evaluation section from the README
  ([`09b6fa3`](https://github.com/climatesense-project/climafacts-kg/commit/09b6fa3bd72c381a7fa6c0ddf7cd3b8a6e852f77))

- Move the evaluation guide out of the README into docs/evaluation.md
  ([`2e41878`](https://github.com/climatesense-project/climafacts-kg/commit/2e41878a8417f4b59ab0ee860378b00192767f3b))

- Shorten the README's model section and keep its details in the report
  ([`b629e90`](https://github.com/climatesense-project/climafacts-kg/commit/b629e903393920f5a0b6368a48fbbc2449694f62))

### Testing

- Read the CLI's error text the same on a CI runner as in a terminal
  ([`2c8d83b`](https://github.com/climatesense-project/climafacts-kg/commit/2c8d83baa1d23bbec2e389152cfbcac3e2625fef))


## v2.4.0 (2026-10-03)

### Bug Fixes

- **classifiers**: Act on the ClimateBERT gate's real labels
  ([`be0515c`](https://github.com/climatesense-project/climafacts-kg/commit/be0515ca6b1afe1b7b5aba125cd91bd7b2140b96))

- **classifiers**: Ask again when a model's output fails validation
  ([`12092c6`](https://github.com/climatesense-project/climafacts-kg/commit/12092c6bb5c60e5928cdd5555f09a69dd6ab343e))

- **classifiers**: Counting cached answers no longer creates or needs the cache file
  ([`6b525f6`](https://github.com/climatesense-project/climafacts-kg/commit/6b525f63130d9574831689685e62614e22cdf82b))

- **classifiers**: Enforce the request timeout around the whole LLM call
  ([`8680229`](https://github.com/climatesense-project/climafacts-kg/commit/8680229335af6a5ec6510b0f3264bc0ab6af47c1))

- **classifiers**: Include every prompt template in the LLM cache key
  ([`0acdc26`](https://github.com/climatesense-project/climafacts-kg/commit/0acdc2647c055fd1f900e3a599a778f509a4f60b))

- **classifiers**: Include the context length limit in the LLM cache key
  ([`7f6059c`](https://github.com/climatesense-project/climafacts-kg/commit/7f6059c9e52244276616a2532044483fa4b7e504))

- **classifiers**: Retry a malformed reply relayed from the provider
  ([`8aa4862`](https://github.com/climatesense-project/climafacts-kg/commit/8aa4862a9a6f888533215bdb2f4c8241d683f857))

- **cli**: Collect and process exit non-zero when a step failed
  ([`50e9313`](https://github.com/climatesense-project/climafacts-kg/commit/50e9313d12242e67acff8c98f50851903934cc9c))

- **collectors**: Collect the Skeptical Science misinformers page again
  ([`7d998e4`](https://github.com/climatesense-project/climafacts-kg/commit/7d998e41648443cade11d951a1ac466eb6dd73c1))

- **collectors**: Give SPARQL queries a default timeout
  ([`451156b`](https://github.com/climatesense-project/climafacts-kg/commit/451156b3d413422e4808f15041f1dc8704bc7db0))

- **collectors**: Skip a URL that cannot be fetched instead of aborting the step
  ([`9082bbb`](https://github.com/climatesense-project/climafacts-kg/commit/9082bbb4a51a285bedd1ebfcf5532d32b0f6664a))

- **collectors**: Time out page fetches and never cache an error response
  ([`4856334`](https://github.com/climatesense-project/climafacts-kg/commit/485633470645be0999aaaa5185e2bdbf4a54fbc6))

- **eval**: Apply [defaults] engine to classifiers that do not set one
  ([`c9a7983`](https://github.com/climatesense-project/climafacts-kg/commit/c9a79836edc6920f1d159cdc5a3347fc15d920b9))

- **eval**: Cap the generated tokens per model in the suite
  ([`3266f1d`](https://github.com/climatesense-project/climafacts-kg/commit/3266f1d4ba755b281127c37b58394f6e7c12f37c))

- **eval**: Exit non-zero when a benchmark combination failed
  ([`9f5d558`](https://github.com/climatesense-project/climafacts-kg/commit/9f5d558009f2a6a7d24dae3e34f48a654a4c6e29))

- **eval**: Keep --dry-run from loading local models
  ([`3195793`](https://github.com/climatesense-project/climafacts-kg/commit/319579386ca27b70fe81bef62d4eb79954e748b3))

- **eval**: Keep a failed call in its own slot when the prompt optimizer scores a batch
  ([`ba76575`](https://github.com/climatesense-project/climafacts-kg/commit/ba76575a30a6a1528c1ce7d65365044fe6a29334))

- **eval**: Keep At a glance short when many models are compared
  ([`24917b8`](https://github.com/climatesense-project/climafacts-kg/commit/24917b818dbaf8af2b3b85e8a7e1bd6966a8ca62))

- **eval**: Keep category scores over every case unless asked otherwise
  ([`4aef5f1`](https://github.com/climatesense-project/climafacts-kg/commit/4aef5f11ca85e5e2dffc3c95f231123f0ba5264d))

- **eval**: Only fold a dataset in the report when it repeats another's cases
  ([`b005096`](https://github.com/climatesense-project/climafacts-kg/commit/b0050962404b2ed91be1098420802a4aa0e4861d))

- **eval**: Render the report when a config failed outright
  ([`e9c711d`](https://github.com/climatesense-project/climafacts-kg/commit/e9c711d4e0000e993ecbeed1371d23292e3670de))

- **eval**: Run qwen3.8-27b on the paid tier
  ([`4aaf024`](https://github.com/climatesense-project/climafacts-kg/commit/4aaf02464861c624b1d08f6390b25ddbeb6024c4))

- **eval**: Run the rate-limited suite models at lower concurrency
  ([`d3e3d14`](https://github.com/climatesense-project/climafacts-kg/commit/d3e3d14c9055c3f8aa80a4a7d1c7c3179f7462a3))

- **eval**: Suite settings for qwen3.8-flash and mistral-large-2512
  ([`057276d`](https://github.com/climatesense-project/climafacts-kg/commit/057276d8462929e4648a9c7101e57fa9de6a8207))

### Documentation

- Add hardware guidance and measured gate effect to the model recommendations
  ([`42d055e`](https://github.com/climatesense-project/climafacts-kg/commit/42d055e599533840e841cfe58a370026edd0bef1))

- Add model recommendations from the standard eval suite
  ([`fa467c4`](https://github.com/climatesense-project/climafacts-kg/commit/fa467c42608763197a8dd805cf625a6e17d255f7))

- Add review context and local hardware results to the report and the README
  ([`605e7e3`](https://github.com/climatesense-project/climafacts-kg/commit/605e7e37cd57624c54073a5241de4388610bb5a3))

- Add the model selection report with charts and link it from the README
  ([`769e2b4`](https://github.com/climatesense-project/climafacts-kg/commit/769e2b42395ea6395e951d80310e1c825a6a53d8))

- Add the prompt comparison to the model recommendations
  ([`8af2184`](https://github.com/climatesense-project/climafacts-kg/commit/8af2184674bacf71f8c6828d660f5561c720ee4d))

- Add the tuned prompt's balanced-score results for five models
  ([`0e9343e`](https://github.com/climatesense-project/climafacts-kg/commit/0e9343e066d02f1b1eee337d189855ec716c213a))

- Add the weighting sensitivity and the simulated gate to the model selection report
  ([`cf7af74`](https://github.com/climatesense-project/climafacts-kg/commit/cf7af74a095b43aa12a7991459dc395c1155ae3b))

- Add whole-graph cost and time estimates and Mistral guidance
  ([`587c511`](https://github.com/climatesense-project/climafacts-kg/commit/587c5110c00f440661bc1d45a5108200ba78721e))

- Bring the README in line with the eval plan, cache and command names
  ([`56527ba`](https://github.com/climatesense-project/climafacts-kg/commit/56527bac2d4d424e9179b1c9c967e32a3a0187e0))

- Correct what process --classifier llm runs and where the gate applies
  ([`5ef22d2`](https://github.com/climatesense-project/climafacts-kg/commit/5ef22d26dcfc85efb11d305f475ffc3b8211bc64))

- Fix stale wording found in review; small cleanups
  ([`10fd465`](https://github.com/climatesense-project/climafacts-kg/commit/10fd465ab158d3e042ec3aafdd2c1635c3592016))

- Point the README and the tuned preset at the balanced-score results
  ([`74ccf7c`](https://github.com/climatesense-project/climafacts-kg/commit/74ccf7c26c85944497b0f4a0a85094679913d5af))

- Record GLM-5.3-Flash's licence and size from its model card
  ([`4d530c7`](https://github.com/climatesense-project/climafacts-kg/commit/4d530c70db156f4832d666907a3d979dea54724a))

- Record the prompt optimisation experiment and the tuned preset's results
  ([`8dff395`](https://github.com/climatesense-project/climafacts-kg/commit/8dff3952744288403384b879ef7d74a974aeaecb))

- Replace estimated costs with measured per-call costs
  ([`e0d6a11`](https://github.com/climatesense-project/climafacts-kg/commit/e0d6a11114813b7d9648062a97774f76a187c44e))

- Split the eval paragraph in CLAUDE.md into headed bullets
  ([`3976a1a`](https://github.com/climatesense-project/climafacts-kg/commit/3976a1a8943276cd41d71085535273a5017f343b))

- Sync the README with the presets and the process options
  ([`e5fc0c5`](https://github.com/climatesense-project/climafacts-kg/commit/e5fc0c52e2215da0f02d695e92c4d302f47e8512))

- Weight category accuracy 75% and false alarms 25% in the balanced score
  ([`d266627`](https://github.com/climatesense-project/climafacts-kg/commit/d2666277e30926bb8046a088ddfdf9cdcb9a3bba))

- **eval**: State published sizes for five suite models
  ([`325c214`](https://github.com/climatesense-project/climafacts-kg/commit/325c214ffd4ac500eb6098aad56d30f5af748059))

### Features

- **builders**: Describe the classifier that produced each CARDS label
  ([`d46dcb2`](https://github.com/climatesense-project/climafacts-kg/commit/d46dcb23718d401ce83357bc47acb7c71bedcd20))

- **classifiers**: Add the experimental xplainnlp-nslp-tuned preset
  ([`d4a6493`](https://github.com/climatesense-project/climafacts-kg/commit/d4a6493559eae9f9133781aed3e11e1a57131978))

- **classifiers**: Pass provider-specific request fields to the LLM
  ([`74c2466`](https://github.com/climatesense-project/climafacts-kg/commit/74c24666fbbfc21f12b05918197b164e3a8a39b8))

- **classifiers**: Time out slow LLM requests and retry them
  ([`70d4830`](https://github.com/climatesense-project/climafacts-kg/commit/70d483001a22d5ddf10d666bdefbe16522f9abe8))

- **cli**: Choose the LLM preset, model, provider and ClimateBERT gate in process
  ([`d67ff88`](https://github.com/climatesense-project/climafacts-kg/commit/d67ff880ea59a416b60e24fe85f12fac3f5df2af))

- **data**: Describe the classifier behind each CARDS label
  ([`067bc28`](https://github.com/climatesense-project/climafacts-kg/commit/067bc281ae26a99967130cac1c7871f0d6b671b8))

- **eval**: Averages across benchmarks in the report
  ([`a55cf5e`](https://github.com/climatesense-project/climafacts-kg/commit/a55cf5e06aa1760379271a79262854bd4b101001))

- **eval**: Hierarchical F1 on the detected category cases, plotted against size
  ([`40bd05b`](https://github.com/climatesense-project/climafacts-kg/commit/40bd05bcb84a6218a0eb667d5ebccbbeba3a6db6))

- **eval**: Keep narrative detection and the CARDS category apart
  ([`b5e3a52`](https://github.com/climatesense-project/climafacts-kg/commit/b5e3a525df9a6442ffa3abce80a882f1d271e057))

- **eval**: Let the prompt optimizer train on no-narrative documents and score on held-out cases
  ([`4de390c`](https://github.com/climatesense-project/climafacts-kg/commit/4de390ce56009ff50b7f3f21b16d024174fea10f))

- **eval**: Make the HTML report easier to read
  ([`7e90615`](https://github.com/climatesense-project/climafacts-kg/commit/7e90615e106d99db92a0716f953dc85402c93acc))

- **eval**: More concurrency for the suite
  ([`50672af`](https://github.com/climatesense-project/climafacts-kg/commit/50672af3fb118fef2fddc9ea5e3e8be418b6417d))

- **eval**: More Qwen, Mistral and open-weight models in the suite
  ([`f190332`](https://github.com/climatesense-project/climafacts-kg/commit/f1903325715de9580ef3dad643454c644653463f))

- **eval**: Plot result against model size and rank many models
  ([`0217a91`](https://github.com/climatesense-project/climafacts-kg/commit/0217a91b675274f252dece44bef0b6c1d88f85b7))

- **eval**: Record model size with a saved run
  ([`5897f4d`](https://github.com/climatesense-project/climafacts-kg/commit/5897f4d66f0a78637cf7d0ff115791089e24f7b7))

- **eval**: Report exact match on category cases and flag weak baselines
  ([`1fd64b0`](https://github.com/climatesense-project/climafacts-kg/commit/1fd64b01454c7cd4c4477a8920e85c8f84a0b0d8))

- **eval**: Run the suite with more concurrency
  ([`ef67944`](https://github.com/climatesense-project/climafacts-kg/commit/ef67944c20e4c0d41c33042755bc71eaa1035405))

- **eval**: Show cached and new paid calls in the benchmark plan
  ([`fbe6baa`](https://github.com/climatesense-project/climafacts-kg/commit/fbe6baa5a4206829d541f468eb0ef0e981711c01))

- **eval**: Standardise the report per benchmark
  ([`ccb7adf`](https://github.com/climatesense-project/climafacts-kg/commit/ccb7adf1510110ef85042c673b689839eec57884))

- **eval**: The same shape for every benchmark in the report
  ([`63703a0`](https://github.com/climatesense-project/climafacts-kg/commit/63703a0f18ca15fb61681ab60bcafdd20d33091d))

- **eval**: The standard full-evaluation suite config
  ([`f77773f`](https://github.com/climatesense-project/climafacts-kg/commit/f77773f27dbcfe07b6b14c1099e1fe4dddab3fe7))

### Refactoring

- **classifiers**: Store the tuned prompt as readable lines and rebuild its JSON wrapper
  ([`25b2343`](https://github.com/climatesense-project/climafacts-kg/commit/25b2343516d30b5fb52a7b6c923db38b72f4587c))

- **eval**: Evaluate() is one benchmark config; drop the dead report evaluators
  ([`abc9bab`](https://github.com/climatesense-project/climafacts-kg/commit/abc9bab4feac5cfa2836140f43a4cdf5b8e9fb1b))

### Testing

- Cover LLM batch failure isolation, caching and context routing
  ([`f11fc83`](https://github.com/climatesense-project/climafacts-kg/commit/f11fc83c88536640b7270e76538d53a7db3bb824))


## v2.3.0 (2026-10-02)

### Bug Fixes

- **classifiers**: Read classification cache entries written before the shared cache
  ([`464b05c`](https://github.com/climatesense-project/climafacts-kg/commit/464b05c01d2d7c3e3c8ccf0372cc62264e20fabf))

- **eval**: Keep dataset labels distinguishable in the compact benchmark table
  ([`7212ff4`](https://github.com/climatesense-project/climafacts-kg/commit/7212ff48231f80a5fb719f96f5595c18598a1bb6))

### Chores

- Refresh GitHub contributors
  ([`a849bc7`](https://github.com/climatesense-project/climafacts-kg/commit/a849bc70713488c87463b322ddb0a6f9a466840c))

### Documentation

- Remove agent design specs and plans from the repo
  ([`d793ffd`](https://github.com/climatesense-project/climafacts-kg/commit/d793ffd429d23cfc041623ba31220b1569385fec))

### Features

- **eval**: Eval command group and config-driven benchmark
  ([`8d50157`](https://github.com/climatesense-project/climafacts-kg/commit/8d501572f12a6941db001c417774115529358e28))

- **eval**: Paired significance for context and model comparisons
  ([`c70a5a0`](https://github.com/climatesense-project/climafacts-kg/commit/c70a5a02242287d7304d35603af165724a0a8cd1))

- **eval**: Score the climate-or-not decision on not-climate documents
  ([`3610129`](https://github.com/climatesense-project/climafacts-kg/commit/36101290fb575180c207038910272d43bfcf98b6))


## v2.2.0 (2026-10-01)

### Bug Fixes

- **eval**: Benchmark on the shared scoring and report reliability columns
  ([`e4d49f7`](https://github.com/climatesense-project/climafacts-kg/commit/e4d49f7a762dce42017f08845309d664363c1674))

- **eval**: Close the remaining review-context edge cases
  ([`817ac6d`](https://github.com/climatesense-project/climafacts-kg/commit/817ac6db0a1e9acd0ac5a23e15404a291de151b7))

- **eval**: Drop page boilerplate and verdict headlines from review context
  ([`7166cc8`](https://github.com/climatesense-project/climafacts-kg/commit/7166cc8f3d5547fcea7522fbb4c9d36d2c78095c))

- **eval**: Fold depth-3 labels, keep counts integral and harden scoring edge cases
  ([`cfff819`](https://github.com/climatesense-project/climafacts-kg/commit/cfff8198e03bae7d3e156e5721d8d6a1cfee329e))

- **eval**: Keep CimpleKG review fetches under the URL and rate limits
  ([`43835b1`](https://github.com/climatesense-project/climafacts-kg/commit/43835b1af003e1cd1d7dc0f0cfcdc1579c644dc7))

- **eval**: Keep multi-run reports distinct and failures visible
  ([`ca0c995`](https://github.com/climatesense-project/climafacts-kg/commit/ca0c995fbec5ea653e5379dbd97e6efc4fddde8e))

- **eval**: Keep the prompt optimizer training claim-only
  ([`fe47945`](https://github.com/climatesense-project/climafacts-kg/commit/fe4794588478f4d86a14bab9804fddf06c54a313))

- **eval**: Report how many cases carried context in each benchmark row
  ([`04b9a21`](https://github.com/climatesense-project/climafacts-kg/commit/04b9a213600aa2ce0d369c8d0ab7e108a83822d2))

- **eval**: Score failed predictions as wrong and unify the not-related code
  ([`a71a6df`](https://github.com/climatesense-project/climafacts-kg/commit/a71a6df30e363a6089d5d7971410ba48012b858b))

### Continuous Integration

- Download Pages assets with authenticated gh release download
  ([`31ccd71`](https://github.com/climatesense-project/climafacts-kg/commit/31ccd712290d33e55060fe870d7c557d7f0e005f))

### Documentation

- Design for review context in the CARDS eval datasets
  ([`b7adf4c`](https://github.com/climatesense-project/climafacts-kg/commit/b7adf4c077ea6eb817dcde81480e6f6bcc8259ce))

- Design for saved, comparable and visual eval reporting
  ([`d61027f`](https://github.com/climatesense-project/climafacts-kg/commit/d61027fe00e51aa7943acc614a85892e38f19171))

- Document review context for the eval datasets
  ([`b7a59d2`](https://github.com/climatesense-project/climafacts-kg/commit/b7a59d2d00a731d0ffaf6216d6b0fa06a8673638))

- Implementation plan for review context in the CARDS eval datasets
  ([`6db06a4`](https://github.com/climatesense-project/climafacts-kg/commit/6db06a43ab8782deeeba4723d3f886278a56d9b8))

- Implementation plan for saved, comparable and visual eval reporting
  ([`e6912aa`](https://github.com/climatesense-project/climafacts-kg/commit/e6912aa6314593980ca994d88089595464fe643d))

- Make review-context selection sentence-based in the eval design
  ([`d9daa10`](https://github.com/climatesense-project/climafacts-kg/commit/d9daa1009713fd7f89e15d7132526ac76584b1ab))

- Require deterministic, LLM-free context preparation in the eval design
  ([`f338518`](https://github.com/climatesense-project/climafacts-kg/commit/f3385180818c4620af9328b012d56bdc00284a4f))

- Update review-context notes after the branch review
  ([`2998147`](https://github.com/climatesense-project/climafacts-kg/commit/299814713e56dca994e9924de62ba6dce89945c9))

- Update test count
  ([`01e8f00`](https://github.com/climatesense-project/climafacts-kg/commit/01e8f00fd19b5956ad3e53e3d604711c92345f3e))

### Features

- **cli**: Add eval-context command to build the review-context sidecar
  ([`2f0345e`](https://github.com/climatesense-project/climafacts-kg/commit/2f0345e3d52fdbf2c93768eddd8c36d3883cd42e))

- **cli**: Add eval-report and document saved runs
  ([`b5639cc`](https://github.com/climatesense-project/climafacts-kg/commit/b5639ccf8da0d6d8c53eff372988c565a7d1c859))

- **eval**: Add a self-contained HTML report with inline SVG charts
  ([`29f6deb`](https://github.com/climatesense-project/climafacts-kg/commit/29f6deb32ccd99ed6ed0b26baf3ec82098639d21))

- **eval**: Add deterministic sentence-based review context selection
  ([`c8a965f`](https://github.com/climatesense-project/climafacts-kg/commit/c8a965f2d55983de9eaafea6484ef8d44d1f3d6b))

- **eval**: Add saved benchmark runs with bootstrap intervals and paired context analysis
  ([`49b6c8d`](https://github.com/climatesense-project/climafacts-kg/commit/49b6c8d7e4e3ec0e4ba9b731e6ad25489b52f377))

- **eval**: Attach selected review context to the ClimateSense datasets
  ([`e80531e`](https://github.com/climatesense-project/climafacts-kg/commit/e80531e2b8fd51bc13da072920fa981b146ab4fb))

- **eval**: Build a review-context sidecar from local inputs and CimpleKG
  ([`11d3fc1`](https://github.com/climatesense-project/climafacts-kg/commit/11d3fc197fbab027c236e6807baaa2044e4b5a96))

- **eval**: Compact benchmark table with intervals and a context-effect view
  ([`9d78b30`](https://github.com/climatesense-project/climafacts-kg/commit/9d78b3084049b5b8ea80686507797eab69137b82))

- **eval**: Compare context on the covered subset and warn on sparse coverage
  ([`fc2083c`](https://github.com/climatesense-project/climafacts-kg/commit/fc2083c7670f27700223531878d5bbed1ff1c5e1))

- **eval**: Evaluate with and without review context
  ([`24f3cf4`](https://github.com/climatesense-project/climafacts-kg/commit/24f3cf4c066512fca72fdd94ebb93b19fdb2189a))

- **eval**: Make review context opt-in for the ClimateSense datasets
  ([`c3d88b6`](https://github.com/climatesense-project/climafacts-kg/commit/c3d88b6ed0977fdcd198d6fa8afc795d59879822))

- **eval**: Save benchmark runs with per-case rows and bootstrap intervals
  ([`e39fd11`](https://github.com/climatesense-project/climafacts-kg/commit/e39fd1142c24df1a2f9480f942fe939d23ef20bd))

- **eval**: Show failures, baseline and reliability columns in the terminal and report
  ([`b7824d5`](https://github.com/climatesense-project/climafacts-kg/commit/b7824d558b4aad8c6ca24bc39e0cc042c58ad6c9))


## v2.1.4 (2026-09-29)

### Bug Fixes

- **llm**: Count each text once in the classification progress bar
  ([`b5cab1e`](https://github.com/climatesense-project/climafacts-kg/commit/b5cab1e7dae4f52f8f1ad6c402628319279c0a30))

- **llm**: Reject a contexts list whose length differs from texts
  ([`cf69186`](https://github.com/climatesense-project/climafacts-kg/commit/cf69186377bbd6dd767f0ff42efdc120166d57d5))

### Chores

- Default TOKENIZERS_PARALLELISM to false
  ([`42b4080`](https://github.com/climatesense-project/climafacts-kg/commit/42b408045c2b991952be7aae6ef0298af0ea0f67))

### Documentation

- Update CLAUDE.md for uv, releases, builders and tests
  ([`e700abf`](https://github.com/climatesense-project/climafacts-kg/commit/e700abf9b87c2ece43e0df64ad71ae41fec5cbb4))


## v2.1.3 (2026-09-29)

### Bug Fixes

- Raise on mismatched lengths instead of silently truncating zip()
  ([`b8cc20d`](https://github.com/climatesense-project/climafacts-kg/commit/b8cc20d1f634e36d18ce50cc34877521e44af0f3))

- **builders**: Stop half-built ClaimReview nodes leaking into the graph
  ([`54f4f7b`](https://github.com/climatesense-project/climafacts-kg/commit/54f4f7b06cc938ccba7192c068bf3caeed21d9c4))

- **builders**: Strip presigned-URL credentials when emitting URLs
  ([`22bd8f1`](https://github.com/climatesense-project/climafacts-kg/commit/22bd8f1f7c9ad98ae650e2bd8e65eecd4a2e41b0))

- **data**: Rebuild graph without half-built ClaimReview and credential URL
  ([`a4fa54c`](https://github.com/climatesense-project/climafacts-kg/commit/a4fa54cb1b9ef0880a3d2c9f0c339ef6ae8a5ca8))

### Build System

- Bump python-semantic-release to v10
  ([`914a664`](https://github.com/climatesense-project/climafacts-kg/commit/914a66485c53dad335aa5c31e948b4e6cdaea6c3))

- Migrate from poetry to uv
  ([`dab0919`](https://github.com/climatesense-project/climafacts-kg/commit/dab0919f6979ec0da8873270894e0a983347faa1))

### Chores

- Add uv-lock pre-commit hook
  ([`aab5874`](https://github.com/climatesense-project/climafacts-kg/commit/aab587409580bd004dd11c3231f24a8bde55b6f1))

### Continuous Integration

- Harden release workflow and install tooling via uv
  ([`e90fd64`](https://github.com/climatesense-project/climafacts-kg/commit/e90fd641beee95265fad60cfc589fdc5a77c9f6d))

- Set semantic-release changelog mode to update explicitly
  ([`44945ae`](https://github.com/climatesense-project/climafacts-kg/commit/44945ae6978d4215cec0c580f2c75e731687eda3))

### Refactoring

- Make zip() strictness explicit and drop the B905 ignore
  ([`182b27c`](https://github.com/climatesense-project/climafacts-kg/commit/182b27ce37f18277ad9aae902fc494c6399ef8b6))


## v2.1.2 (2026-09-18)

### Bug Fixes

- **ci**: Add missing <!-- version list --> insertion marker to CHANGELOG.md
  ([`7c7642e`](https://github.com/climatesense-project/climafacts-kg/commit/7c7642e4f85e66aa5edacd3c90ff6c7089038676))

### Continuous Integration

- Add debug verbosity to semantic-release version, prior fix unconfirmed
  ([`56c635e`](https://github.com/climatesense-project/climafacts-kg/commit/56c635ea736c611babd5f9a50cbf315ff0aed76b))


## Unreleased

### Continuous Integration

- Add debug verbosity to semantic-release version, prior fix unconfirmed
  ([`56c635e`](https://github.com/climatesense-project/climafacts-kg/commit/56c635ea736c611babd5f9a50cbf315ff0aed76b))


## v2.1.1 (2026-09-18)

### Bug Fixes

- **ci**: Fetch tags before semantic-release version, not after
  ([`587cb62`](https://github.com/climatesense-project/climafacts-kg/commit/587cb62d808023f4af6d32e7d7d3abed16d82517))

### Documentation

- Backfill CHANGELOG.md missing history since v1.1.0
  ([`7c6dffa`](https://github.com/climatesense-project/climafacts-kg/commit/7c6dffa14373235f341e3a4cd6af952a7e15160f))


## Unreleased

### Bug Fixes

- Three issues from architecture review
  ([`dff52c1`](https://github.com/climatesense-project/climafacts-kg/commit/dff52c185f3950130c775baeb449802fe0286ef3))

- builders/climafactskg.py: cards_category exclusion only checked "0_0" (LLM engine's not-related
  sentinel), not "0" (transformer/ matcher's) — so transformer-classified SkS arguments (the default
  process engine) got a bogus SDO.about link to the "not relevant" CARDS taxonomy node.
  builders/cimplekg.py already excluded both correctly; climafactskg.py now matches it. - utils.py:
  fetch_url_content's cache_dir/cache_expiry defaults were os.getenv()/timedelta() calls evaluated
  once at import time, so env var changes after import (or before load_dotenv() runs) were silently
  ignored. Now read inside the function body, matching query_sparqlendpoint's existing correct
  pattern. - endpoints.py: serve_endpoint's own default host was "0.0.0.0" (network-exposed); the
  CLI wraps it with a safer 127.0.0.1 default but calling it directly (script, notebook, test) got
  no such protection. Default now matches the CLI.

### Documentation

- Replace two stale TODOs with concrete investigated findings
  ([`5e33077`](https://github.com/climatesense-project/climafacts-kg/commit/5e33077c6b5851f4ac7855a26184b195c172a1cc))

climatesensekg.py: checked the live endpoint's schema for a climate-relatedness pre-filter.
  schema:mentions dbpedia:Climate_change exists on ~13k ClaimReviews and could filter the query, but
  decided against it — permanent, silent recall loss for any climate claim not tagged with that
  exact entity, with no way to detect the exclusion later. Classifying everything costs more but has
  no recall risk.

builders/climafactskg.py: the "cross ref definitions and citations" TODO was half done and half
  vague. Citations are already implemented (sksreferenceskg.py:generate_citations_graph).
  Definitions (glossary terms discarded by parse_skstiptionary_references' citation=="4" filter) are
  not — documented the concrete remaining scope (parser, storage, RDF schema choice, builder
  function) instead of a one-line TODO, since it's comparable in size to the citations feature
  itself.

- **classifiers**: Fill gaps left by cache/interface unification
  ([`f483485`](https://github.com/climatesense-project/climafacts-kg/commit/f4834855d2cbdb4d98e8734ba56ec3c07ed7c3fe))

- Rewrite classify_batch's stale docstring (still described the old manual batch-read/write steps,
  not the current ClassificationCache delegation). - Document the shared cache_path,
  CARDSClassifierBase, and per-engine context support in README (was CLAUDE.md-only). - Add
  --context to the CLI's classify command (all three engines accept it now) and let --cache-path
  apply to the transformer engine too, not just LLM. - Add tests: matcher context joining/batch
  behavior, cache_path forwarding from batch_classify_cards_category to both engines.

### Features

- **collectors**: Persist is_climate_related instead of collapsing it
  ([`19876bc`](https://github.com/climatesense-project/climafacts-kg/commit/19876bc794ded5805a822610c112d0e58c92b113))

Both engines already compute a relatedness signal internally (LLM's CARDSOutput.is_climate_related,
  transformer's binary-gate result) but discarded it into the "0"/"0_0" category sentinel with no
  separate trace. Derive and store is_climate_related on every classified entry in
  batch_classify_cards_category, uniformly across engines (category not in NOT_RELATED_CATEGORIES),
  with zero classifier interface changes. One LLM-only edge case (is_climate_related=True,
  cards_category=None) stays unrecoverable at this level — documented in llm/classifier.py's
  docstring and the relatedness-vs-category memory note rather than solved via a return-type break.

- **utils**: Cache SPARQL query results (disk + in-process)
  ([`66902c1`](https://github.com/climatesense-project/climafacts-kg/commit/66902c1a539ea247ca8069bdfd6d5e23db648f6e))

collect() and process() each call fetch_claims() independently, so a normal collect-then-process run
  re-downloaded the same ~260k+137k row SPARQL result sets twice with no caching at all — a standing
  TODO in both collectors.

query_sparqlendpoint now caches to disk (keyed by endpoint+query, default 12h expiry via
  CLIMAFACTSKG_SPARQL_CACHE_EXPIRY — these endpoints refresh roughly daily) so repeat calls across
  separate CLI invocations reuse the last fetch instead of re-downloading. Also wrapped in lru_cache
  for free zero-I/O reuse within a single process.

Removes the now-stale "TODO Cache query results" comments from both collectors. Adds
  cache-hit/cache-expiry tests; existing tests updated to use per-test cache_dir so they don't
  collide with each other now that results are cached.

### Performance Improvements

- **classifiers**: Share CARDS classification cache across sources
  ([`a512dd1`](https://github.com/climatesense-project/climafacts-kg/commit/a512dd1799f1ee36b749130437b7027e16aefc5a))

CimpleKG and ClimateSenseKG independently classified identical claim text since each collector built
  its own classifier with no cache. Add cache.py:ClassificationCache (shared get-or-compute over a
  Preserve SQLite file) used by both CARDSClassifier (transformer, new cache_path support) and
  CARDSLLMClassifier (retrofit of its existing preclassifier/output caches onto the shared helper,
  cache key bytes unchanged so existing cache files stay valid). Thread cache_path through
  collectors/utils.py and the CLI's `process --cache-path` (default: one shared file across all
  sources) so identical text is classified once, not once per source.

### Refactoring

- Centralize logging config, remove it from library modules
  ([`45cfaa9`](https://github.com/climatesense-project/climafacts-kg/commit/45cfaa9160c20ff6b1b364442e7b73dc76c40f32))

Six library modules (builders/climafactskg.py, builders/cimplekg.py, builders/sksreferenceskg.py,
  collectors/cimplekg.py, collectors/climatesensekg.py, collectors/skepticalscience.py) each called
  logging.basicConfig(level=logging.INFO) at import time. Since basicConfig() no-ops once the root
  logger already has a handler, only whichever of these six happened to import first actually took
  effect — an accidental, import-order-dependent result, and a library anti-pattern regardless (it
  forces logging config on anyone embedding climafactskg as a library, not just the CLI). Moved the
  one call that matters to cli.py's module top level, the actual application entry point; library
  modules keep only logging.getLogger(__name__). optimization.py/eval.py's own basicConfig calls are
  untouched — both already properly guarded inside `if __name__ == "__main__":` blocks.

- Logger.* over bare logging.*, extract shared new_graph helper
  ([`eb2c94d`](https://github.com/climatesense-project/climafacts-kg/commit/eb2c94d685c420c5941627e63261c2563105f5c3))

- collectors/skepticalscience.py and all three builders/*.py called the root logger directly
  (logging.info/error/warning) instead of a module logger — inconsistent with every other module,
  and it makes log output impossible to filter/attribute by source module. Add logger =
  logging.getLogger(__name__) to each and switch all calls. - Extract
  builders/utils.py:new_graph(bindings) — the Graph()+NamespaceManager(Graph())+bind() sequence was
  repeated identically (aside from which prefixes) across builders/climafactskg.py, cimplekg.py, and
  sksreferenceskg.py. One helper, three call sites.

- Remove legacy/dead code
  ([`d372b58`](https://github.com/climatesense-project/climafacts-kg/commit/d372b586342522fafb12012f8adf7db946eb2289))

- Remove cards_classification() (transformer.py) — unused, untested, explicitly marked "legacy
  single-use helper"; CARDSClassifier is the maintained path. Drop it from __init__.py's lazy-load
  registry and __all__/docstring. - Remove deserialize_datetime() (utils.py) — no caller anywhere;
  serialize_datetime (its used counterpart) is untouched. - Remove bib["title"] duplicate field in
  parse_skstiptionary_references (parsers/skepticalscience.py) — same value as bib["header"],
  explicitly marked "kept for backward compatibility". Update its one reader
  (sksreferenceskg.py:generate_references_graph) to use "header" directly, and the function's
  docstring. - Drop a dead duplicate docstring statement in remove_html_tags.

- **builders**: Extract shared add_cards_category_link helper
  ([`3f335e5`](https://github.com/climatesense-project/climafacts-kg/commit/3f335e5a1b92042824ba4bf5f280e1ddaf4e8046))

builders/climafactskg.py and builders/cimplekg.py each hand-rolled the same SDO.about/SDO.subjectOf
  triple-adding logic with its own not-related-sentinel exclusion check inline — exactly the
  duplication that let the two drift out of sync (the "0" exclusion bug fixed earlier this session).
  Extract one add_cards_category_link(g, cards_ns, subject, cards_category) in cimplekg.py, used by
  both builders, so the exclusion list (NOT_RELATED_CARDS_CATEGORIES) has one home instead of two
  copies.

- **builders**: Extract shared safe_uriref, dedupe percent-encoding
  ([`ae11fa5`](https://github.com/climatesense-project/climafacts-kg/commit/ae11fa5467991ddd2c1d13521e53a52a67b62d06))

climafactskg.py's _safe_uriref (percent-encode a URL for a safe IRI) had its exact safe-char set
  (":/?#[]@!\$&'()*+,;=-._~%") duplicated inline in sksreferenceskg.py's reference-URL triple,
  rather than reused. Moved to builders/utils.py as safe_uriref, used by both. sksreferenceskg.py's
  DOI-specific quote() call (different safe set, slash-critical) is untouched — not the same case.

- **classifiers**: Unify CARDS classifier interface
  ([`284d6cd`](https://github.com/climatesense-project/climafacts-kg/commit/284d6cd0d1147de49113ce600f0502cc825d2e1a))

CARDSMatcher, CARDSClassifier (transformer), and CARDSLLMClassifier did the same job with drifting
  signatures — only the LLM engine accepted context. Add base.py:CARDSClassifierBase (ABC:
  classify(text, context=None), classify_batch(texts, contexts=None)) and have all three inherit it.
  Matcher and transformer gain real context support (joined into the text, matching
  ClimateBertClassifier's existing convention); the LLM engine already matched the shape. eval.py's
  evaluate()/benchmark_configs() context gate now checks isinstance(classifier, CARDSClassifierBase)
  instead of a private LLM-only attribute, so matcher/transformer now actually receive dataset
  context during evaluation instead of silently dropping it.

- **cli**: Route _validate_graph output through logger, not typer.echo
  ([`198f322`](https://github.com/climatesense-project/climafacts-kg/commit/198f322e5dc861ff7722ce86749fbb2c7b053c09))

Was a deliberate stdout/stderr split (typer.echo for CLI-command output, logger for progress) — user
  asked for consistency with the rest of the pipeline over script-parseable stdout, so switched all
  of it (stats, OK, FAILED) to logger.info/logger.error.

- **collectors**: Declare a shared claim-review pipeline instead of implicit reuse
  ([`eed3d7a`](https://github.com/climatesense-project/climafacts-kg/commit/eed3d7a3dde2ec0aafbb2a1793d6046a5d611752))

climatesensekg.py imported process_all directly from cimplekg.py — no wrapper, no declared contract,
  working only because both SPARQL queries happen to alias columns identically
  (rev/date_published/text). A future source with a different shape would have silently broken or
  written wrong data.

Moves the generic (non-source-specific) logic into collectors/utils.py as
  process_claim_reviews/classify_claim_reviews/process_all_claim_reviews, documented as the explicit
  contract any SPARQL ClaimReview source can reuse. cimplekg.py and climatesensekg.py each keep
  their own fetch_claims (source-specific) plus thin, documented wrapper functions delegating to the
  shared pipeline — no more accidental cross-module dependency, and cli.py's call sites are
  unchanged.

Adds tests/test_collectors_utils.py covering the shared pipeline directly.

- **llm**: Derive _TAXONOMY_CODE_SET from TaxonomyCode via get_args
  ([`b50d3a1`](https://github.com/climatesense-project/climafacts-kg/commit/b50d3a1f72b4ad2fd0c3fc7e8f24685a571f22f0))

_TAXONOMY_CODE_SET hand-retyped every member of the TaxonomyCode Literal right above it, with a
  comment admitting "must stay in sync with the Literal above" — the classic sign of a duplicate
  nobody wants to touch. typing.get_args() extracts a Literal's members at runtime, so the set can
  be derived instead of duplicated; the two can no longer drift out of sync by construction.


## v2.0.2 (2026-09-16)

### Bug Fixes

- **cli**: Isolate collect() steps so one failure doesn't skip the rest
  ([`2a4be6e`](https://github.com/climatesense-project/climafacts-kg/commit/2a4be6e073119e1540088372625569e9d790a03e))

collect() ran its 5 fetch calls as a flat sequence — a live 504 from CimpleKG's SPARQL endpoint once
  took the whole command down, skipping the unrelated ClimateSenseKG/SkepticalScience steps after
  it. process() already had this fix; collect() didn't.

Wraps each step in try/except, logging and continuing on failure, same pattern as process(). Adds
  tests/test_cli_collect.py covering both the happy path and the isolation behavior.


## v2.0.1 (2026-09-16)

### Bug Fixes

- **ci**: Don't double-nest gh-pages output under climafacts-kg/
  ([`00ca29b`](https://github.com/climatesense-project/climafacts-kg/commit/00ca29b81b96e651b6d366aca24eac8f4d888493))

This is a standard GitHub Project Pages site (no CNAME/custom domain), already served at
  https://climatesense-project.github.io/climafacts-kg/ by GitHub's own routing. Adding another
  climafacts-kg/ subfolder inside the published artifact double-nested every file path and left the
  actual site root without an index.html, causing a 404 there.


## v2.0.0 (2026-09-16)

### Continuous Integration

- Nest gh-pages output under climafacts-kg/ to avoid path collisions
  ([`80443b8`](https://github.com/climatesense-project/climafacts-kg/commit/80443b8af76f5219ac4c4156fcfeb25f9c5af808))

Published files now live at climafacts-kg/<file> instead of the Pages root, so this repo's output
  can't collide with another repo's files on a shared org-level Pages site or custom domain.

### Features

- **rdf**: Split CARDS taxonomy into its own namespace
  ([`0f8198f`](https://github.com/climatesense-project/climafacts-kg/commit/0f8198fcf107e1def2bd021f8fc53f50a30a914f))

CARDS concept URIs move from https://purl.net/climatesense/climafactskg/ns# to their own
  https://purl.net/climatesense/cards/ns#. CARDS is a shared taxonomy also used to connect claims in
  CimpleKG, not something owned by ClimaFactsKG, so it shouldn't be nested inside ClimaFactsKG's own
  namespace.

Updates data/cards.ttl, the taxonomy.py metadata, matcher.py's custom-taxonomy SPARQL query, both
  RDF builders (cimplekg.py, climafactskg.py), the SPARQL endpoint's prefix bindings, and publishes
  cards.ttl/cards.rdf as their own release assets and GH Pages files so the new namespace has
  somewhere to 303-redirect to.

BREAKING CHANGE: any external reference to a CARDS concept under the old
  https://purl.net/climatesense/climafactskg/ns#<code> URI now resolves under
  https://purl.net/climatesense/cards/ns#<code> instead. Instance-data URIs (ClaimReview,
  ScholarlyArticle, etc.) are unaffected.

### Breaking Changes

- **rdf**: Any external reference to a CARDS concept under the old
  https://purl.net/climatesense/climafactskg/ns#<code> URI now resolves under
  https://purl.net/climatesense/cards/ns#<code> instead. Instance-data URIs (ClaimReview,
  ScholarlyArticle, etc.) are unaffected.


## v1.6.0 (2026-09-16)

### Bug Fixes

- **build**: Make blank node ids deterministic for reproducible builds
  ([`63e5e0e`](https://github.com/climatesense-project/climafacts-kg/commit/63e5e0e2847ca06f7f31d600a490e85a7dabb38a))

BNode() with no explicit value gets a random id from rdflib each run, which made the Turtle
  serializer's ordering of multi-valued properties (e.g. multiple sc:author entries per reference)
  shuffle on every build even with unchanged source data, producing large spurious diffs.

Derive rating/author/DOI-identifier BNode ids from content (hash_string over article/claim id +
  position) instead. As a side effect, this also deduplicates author/DOI nodes that were
  content-identical but previously always got distinct random ids and could never merge.

- **pipeline**: Fix classification/build bugs, add classifier engine selection, CI, tests, docs
  ([`c48d66f`](https://github.com/climatesense-project/climafacts-kg/commit/c48d66f7c23bb00753e1ad927085247a177fd47b))

Fixes: preset concurrency/preclassifier overrides ignored, batch classification losing all results
  on one item's failure, semaphore held during retry backoff, stale non-English categories never
  cleared, short citation fragments dropped, SPARQL parser crashing on malformed response, GEPA
  context lookup colliding on duplicate claim text, eager heavy imports on classifier package load,
  leaked AWS credential in scraped citation URLs.

Adds: classifier engine selection on `process` (transformer default, matches legacy behavior; llm
  opt-in), `climafactskg validate` command (also run automatically at the end of `build`) to catch
  broken RDF output early, ClimateSenseKG wired into `build`, a CI workflow running ruff + pytest, a
  pyproject extras split so matcher/transformer/eval dependencies are optional, and a test suite (58
  tests) covering the previously-untested pure logic.

### Continuous Integration

- Append knowledge graph stats to GitHub release notes
  ([`294bbf6`](https://github.com/climatesense-project/climafacts-kg/commit/294bbf6ee2d2ed38b567bea2bf6e9f97ccf6ff04))

Reads the released data/climafacts_kg.ttl and appends a stats table (triples, ClaimReviews,
  ScholarlyArticles, citations) to the release body semantic-release already generated, rather than
  replacing it.

### Features

- **classifiers**: Split CARDS classifier into a package, add ClimateSenseKG collector
  ([`5306aa9`](https://github.com/climatesense-project/climafacts-kg/commit/5306aa982f77d716fd1fce0ccf48afe740b6dfc7))

Splits the monolithic classifiers/cards.py into a cards/ package (matcher, transformer, taxonomy,
  evaluators, llm/) and adds a ClimateSenseKG SPARQL collector alongside the existing CimpleKG one.


## v1.5.1 (2026-04-07)

### Bug Fixes

- Normalize text literals to avoid multiline Turtle strings
  ([`9299d51`](https://github.com/climatesense-project/climafacts-kg/commit/9299d51057a60db20a8a8dcf6a450b50df7cac85))

Adds _normalize_text() in the builder to collapse newlines in string literals, producing single-line
  Turtle literals compatible with all strict Turtle parsers. Regenerates climafacts_kg.ttl
  accordingly.


## v1.5.0 (2026-03-11)

### Features

- **kg**: Add SKS references builder for RDF graph generation
  ([`7d5e5d4`](https://github.com/climatesense-project/climafacts-kg/commit/7d5e5d4f8aa5331a3eaf842f88efe563a8281074))

Add a new builder in sksreferenceskg.py to map SkepticalScience references to RDF graphs using
  Schema.org, BIBO, and CiTO vocabularies.

- Implement author parsing, DOI normalisation, and page range splitting - Add functions to generate
  references and citations graphs linking articles to their respective references - Integrate
  logging for tracking reference and citation link processing


## v1.4.0 (2025-11-01)

### Features

- Knowledge graph update
  ([`e41297a`](https://github.com/climatesense-project/climafacts-kg/commit/e41297a53e0afb8c64c59f677b55cb236c575f1f))


## v1.3.0 (2025-09-29)

### Bug Fixes

- Merge changes
  ([`4841993`](https://github.com/climatesense-project/climafacts-kg/commit/48419936bf71f467fe4e723474989849aa24c135))


## v1.2.0 (2025-08-26)

### Features

- Migrate from TinyDB to Preserve (Sqlite backend)
  ([`d82f146`](https://github.com/climatesense-project/climafacts-kg/commit/d82f1462f67811f4d157e2e0337b3b7fb8ac6544))

- Added code for collecting misinformers and quotes - Updated dependencies in pyproject.toml -
  Removed tinydb and tinydb-serialization from dependencies - Added preserve package with version
  ^1.2.1 - Added jupyter package to dev dependencies

- Update namespace path to climatesense namespace and add repository metadata
  ([`5b50435`](https://github.com/climatesense-project/climafacts-kg/commit/5b504352537ed8d14e19c9a92b0c52af7740d3ef))


## v1.1.0 (2025-07-31)

### Documentation

- Fix typo in README.md
  ([`bdae25b`](https://github.com/climatesense-project/climafacts-kg/commit/bdae25b225b4b929c493a542f6e7db7f87f42c8e))

- Update README.md
  ([`4507914`](https://github.com/climatesense-project/climafacts-kg/commit/45079147ebc8fd2ead9ef341762f4fccba7503bf))

### Features

- Add new CARDS classifier based on Jaccard similarity, fix namespace and generated RDF
  ([`ac0a1d2`](https://github.com/climatesense-project/climafacts-kg/commit/ac0a1d2b0c4336c59db4cea5e458d2bcd8dc9ccf))


## v1.0.10 (2025-07-29)

### Bug Fixes

- Reformat workflow
  ([`943f7c3`](https://github.com/climatesense-project/climafacts-kg/commit/943f7c3351fddf8ae650b9dc55c996dab5cbf443))

### Documentation

- Add badge to README.md
  ([`ab896fc`](https://github.com/climatesense-project/climafacts-kg/commit/ab896fc9ede3f4d907e6ef988522888a2ba957b1))


## v1.0.9 (2025-07-29)

### Bug Fixes

- Add env token to workflow
  ([`74ddcff`](https://github.com/climatesense-project/climafacts-kg/commit/74ddcffd2734e1be7fa3179968ae2fe17f7330aa))


## v1.0.8 (2025-07-29)

### Bug Fixes

- Workflow trigger
  ([`ffe0129`](https://github.com/climatesense-project/climafacts-kg/commit/ffe0129147a0e3c784faba377773653c824db089))


## v1.0.7 (2025-07-29)

### Bug Fixes

- Use trigger event for publishing graph
  ([`3cc88ef`](https://github.com/climatesense-project/climafacts-kg/commit/3cc88effc9d23a7660b34b66befc800f89bd4bbe))


## v1.0.6 (2025-07-29)

### Bug Fixes

- File extension in semantic-release.yml
  ([`034992c`](https://github.com/climatesense-project/climafacts-kg/commit/034992c8896ca9a95365ef25ff5ae4e48e8651d5))


## v1.0.5 (2025-07-29)

### Bug Fixes

- Vars in semantic-release.yml
  ([`852466c`](https://github.com/climatesense-project/climafacts-kg/commit/852466cc55c58088518958560ff1ec992f9b411a))


## v1.0.4 (2025-07-29)

### Bug Fixes

- Workflows formatting
  ([`d437208`](https://github.com/climatesense-project/climafacts-kg/commit/d4372089d7370be3811a5e7e5a1f67bafda786fb))


## v1.0.3 (2025-07-29)


## v1.0.2 (2025-07-29)

### Bug Fixes

- Missing comma in semantic-release.yml
  ([`6be5143`](https://github.com/climatesense-project/climafacts-kg/commit/6be514396ba4bbef3441eb61d0bf46907debec35))

- Update TTL conversion in semantic-release.yml
  ([`2f30a7a`](https://github.com/climatesense-project/climafacts-kg/commit/2f30a7a54e41bf9d9432d8c45a152eddb81e0d94))


## v1.0.1 (2025-07-29)


## v1.0.0 (2025-07-29)

### Bug Fixes

- Add .nojekyll to gh-pages-publish.yml
  ([`c549db1`](https://github.com/climatesense-project/climafacts-kg/commit/c549db11a505ea7dc7e93790e458b7eb3a6b9749))

- Change quotes in gh-pages-publish.yml
  ([`19c2456`](https://github.com/climatesense-project/climafacts-kg/commit/19c245644f55790fbed310f5d397406438825a9c))

- Remove token from gh-pages-publish.yml
  ([`25ad03b`](https://github.com/climatesense-project/climafacts-kg/commit/25ad03bfd5251c37bc5ae6f73453b64a2eaf8c44))

- Update formatting of gh-pages-publish.yml
  ([`5cd60d6`](https://github.com/climatesense-project/climafacts-kg/commit/5cd60d6f4328e1cbe4fd93bc803d71643f7b093f))

- Update gh-pages-publish.yml token
  ([`eb64ec6`](https://github.com/climatesense-project/climafacts-kg/commit/eb64ec618a528b37f27c9852ae040ec0e99b4844))

Update token access in gh-pages-publish.yml

- Update semantic-release.yml workflow for not publishing on PyPi
  ([`d68b3d6`](https://github.com/climatesense-project/climafacts-kg/commit/d68b3d6e2e7ab33bdf0e600d4f66cb558908ae83))

- Use RDF instead of TTL in gh-pages-publish.yml
  ([`aa2de5e`](https://github.com/climatesense-project/climafacts-kg/commit/aa2de5e4e08a8724c33e9b911162ffd0b3937767))

### Documentation

- Add SkS mappings to README.md 🗺️
  ([`f3410f8`](https://github.com/climatesense-project/climafacts-kg/commit/f3410f832f8dc193baa92d18711b380da88a8151))

- Create README.md
  ([`2f86c20`](https://github.com/climatesense-project/climafacts-kg/commit/2f86c20ae3e4b305692f3cec7ed49e635cb96a02))

- Prettify README.md 💅🏼
  ([`55f11f3`](https://github.com/climatesense-project/climafacts-kg/commit/55f11f3c0838f79b268ab93b7ec64cb8b19182d0))

### Features

- Add TTL publish action
  ([`28cc8aa`](https://github.com/climatesense-project/climafacts-kg/commit/28cc8aabe9ce6576712c7f8dcbd0ff5e86f046a4))

Create gh-pages-publish.yml GitHub action for uploading the TTL ClimaFactsKG to GH-Pages.

- First version of the ClimaFactsKG source code
  ([`c5ff907`](https://github.com/climatesense-project/climafacts-kg/commit/c5ff90798e7d5f84f48fe56cdd99280972ef4529))


## v0.1.0 (2025-07-26)
