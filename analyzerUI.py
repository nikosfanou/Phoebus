import html
import json

def get_browser_icon(browser_name):
    browser_name = browser_name.lower()

    if browser_name.startswith("chrome"):
        return "../default-files/icons/Chrome.png"

    if browser_name.startswith("firefox"):
        return "../default-files/icons/Firefox.png"

    if browser_name.startswith("webkit"):
        return "../default-files/icons/WebKit.svg"

    if browser_name.startswith("safari"):
        return "../default-files/icons/Safari.png"

    if browser_name.startswith("edge"):
        return "../default-files/icons/Edge.svg"

    if browser_name.startswith("brave"):
        return "../default-files/icons/Brave.png"

    if browser_name.startswith("opera"):
        return "../default-files/icons/Opera.png"

    if browser_name.startswith("tor"):
        return "../default-files/icons/Tor.png"

    return ""

def escape(value):
    return html.escape(str(value))

def format_json(obj):
    return escape(
        json.dumps(
            obj,
            indent=2,
            ensure_ascii=False
        )
    )


def generate_behavior_report_html(all_browser_sections, output_path):
    ### CSS and metadata ###
    html_parts = ["""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">

<title>
Cross Browser Report
</title>

<style>

body {
    font-family: Arial, sans-serif;
    background: #f4f4f4;
    margin: 0;
    padding: 20px;
}

.tabs {
    display: flex;
    gap: 5px;
    margin-bottom: 20px;
    
    position: sticky;
    top: 0;
    z-index: 1000;

    background: #f4f4f4;
    padding-top: 8px;
    padding-bottom: 8px;
}

.tab-button {
    border: none;
    background: #ddd;
    padding: 10px 20px;
    cursor: pointer;
    border-radius: 6px;
}

.tab-button.active {
    background: #4a69bd;
    color: white;
    font-weight: bold;
    box-shadow: 0 0 10px rgba(74,105,189,.5);
}

.tab-content {
    display: none;
}

.tab-content.active {
    display: block;
}

h1 {
    background: #20232a;
    color: white;
    padding: 15px;
    border-radius: 8px;
}

h2 {
    margin-top: 40px;
    background: #2f3542;
    color: white;
    padding: 10px;
    border-radius: 8px;
}

.card {
    background: white;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 25px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    overflow-wrap: break-word;
    word-wrap: break-word;
}

.result-box {
    background: #f8f9fa;
    border-left: 5px solid #4a69bd;
    padding: 15px;
    margin-top: 15px;
    border-radius: 5px;
}

details {
    margin-top: 10px;
}

summary {
    cursor: pointer;
    font-weight: bold;
}
                  
.results-cluster {
    margin-top: 30px;
    margin-bottom: 20px;
    background: #eef4ff;
    border-left: 6px solid #4a69bd;
    border-radius: 8px;
    padding: 12px;
}
                  
.results-cluster summary {
    font-size: 1.25em;
    font-weight: bold;
    cursor: pointer;
}
                  
.cluster-count {
    margin-left: 12px;
    color: #4a69bd;
    font-weight: normal;
}
                  
.result-signature {
    margin-bottom: 10px;
    font-family: monospace;
}

pre {
    background: #272822;
    color: #f8f8f2;
    padding: 10px;
    overflow-x: auto;
    border-radius: 6px;
}

.case {
    margin-bottom: 15px;
    padding: 10px;
    background: #f1f2f6;
    border-radius: 5px;
}

.deployment {
    margin-top: 15px;
    background: #fafafa;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 10px;
}

code {
    background: #eee;
    padding: 2px 4px;
    border-radius: 4px;
}

.rule-card {
    scroll-margin-top: 20px;
}

.highlight {
    outline: 4px solid #4a69bd;
    border-radius: 10px;
}

.highlight-test {
    background: #fff59d;
    border-radius: 4px;
    padding: 2px 4px;
}

.test-entry {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
}

.browser-links {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.browser-icon {
    width: 22px;
    height: 22px;
    cursor: pointer;
}

.browser-icon:hover {
    transform: scale(1.15);
}

</style>
</head>

<body>
"""]

    ### Browser Tabs/buttons ###
    html_parts.append("""
<div class="tabs">
""")

    first = True

    for browser_name in all_browser_sections:

        active = "active" if first else ""

        html_parts.append(
            f"""
<button
    class="tab-button {active}"
    data-browser="{escape(browser_name)}"
    onclick="showTab('{escape(browser_name)}')">

    {escape(browser_name)}

</button>
"""
        )

        first = False

    html_parts.append("</div>")

    ### Browser reports ###
    first_browser = True

    for browser_name, browser_sections in all_browser_sections.items():

        active = "active" if first_browser else ""

        html_parts.append(
            f"""
<div
    id="{escape(browser_name)}"
    class="tab-content {active}">

<h1>
Browser Report:
{escape(browser_name)}
</h1>
"""
        )

        first_browser = False

        global_rule_counter = 1

        for section_name, region_clusters in browser_sections.items():

            html_parts.append(
                f"""
<h2>
Section:
{escape(section_name)}
</h2>
"""
            )

            for behavior_signature_index, (behavior_signature, deployment_clusters) in enumerate(region_clusters.items()):

                html_parts.append(
                    f"""
<div class="results-cluster">

<details open>

<summary>

Cluster #{behavior_signature_index + 1}

<span class="cluster-count">({len(behavior_signature)} distinct results)</span>

</summary>

<ul>
"""
                )

                for result_signature in behavior_signature:

                    html_parts.append(
                        f"""
<li class="result-signature">
{escape(str(result_signature))}
</li>
"""
                    )

                html_parts.append(
                    """
</ul>

</details>
</div>
"""
)

                ### Rule cards ###
                for deployment_signature, cluster in deployment_clusters.items():

                    html_parts.append(
                        f"""
<div
    class="card rule-card">

<h3>
Rule #{global_rule_counter}
</h3>
"""
                    )

                    global_rule_counter += 1

                    ### Test IDs ###
                    html_parts.append(
                        f"""
<details open>

<summary>
Tests ({len(cluster["tests"])})
</summary>

<ul>
"""
                    )

                    for test in sorted(cluster["tests"]):

                        html_parts.append(
                            f"""
<li
    data-test-id="{escape(test)}">

<div class="test-entry">

<span>
{escape(test)}
</span>

<div class="browser-links">
"""
                        )

                        ### Icons linking what the other browsers do for this test. ###
                        for other_browser in all_browser_sections.keys():

                            if other_browser == browser_name:
                                continue

                            icon = get_browser_icon(other_browser)

                            html_parts.append(
                                f"""
<img
    src="{escape(icon)}"
    class="browser-icon"
    title="{escape(other_browser)}"
    onclick="
        jumpToTest(
            '{escape(other_browser)}',
            '{escape(test)}'
        )
    ">
"""
                            )

                        html_parts.append("""
</div>
</div>

</li>
""")

                    html_parts.append("""
</ul>
</details>
""")

                    ### Execution Results for these Test IDs ###
                    html_parts.append(f"""
<details open>
<summary>
Results ({len(cluster["results"])})
</summary>
""")

                    for result, deployment_ids in cluster["results"].items():

                        html_parts.append(
                            f"""
<div class="result-box">

<h4>
Result:
{escape(result)}
</h4>
"""
                        )

                        representative = cluster["tests"][0]

                        representative_result_map = cluster["deployments"][representative]

                        deployments = representative_result_map[result]

                        case_counter = 1
                        seen_cases = set()

                        html_parts.append(
                            "<h4>Cases</h4>"
                        )

                        for deployment in deployments:

                            mechanisms = deployment.get("mechanisms", {})
                            custom_headers = deployment.get("custom_headers")
                            status_code = deployment.get("status_code")

                            if isinstance(status_code, list):
                                status_code.sort()


                            if custom_headers is None:
                                custom_header_groups = [[]]
                            elif not isinstance(custom_headers, list):
                                custom_header_groups = [[custom_headers]]
                            elif custom_headers and isinstance(custom_headers[0], str):
                                custom_header_groups = [custom_headers]
                            else:
                                custom_header_groups = custom_headers


                            mechanism_lines = []

                            for mech_name, values in mechanisms.items():

                                for value_obj in values:

                                    value = value_obj["value"]

                                    if isinstance(value, list):
                                        for v in value:
                                            mechanism_lines.append(f"{mech_name}: {v}")
                                    else:
                                        mechanism_lines.append(f"{mech_name}: {value}")

                            
                            for header_group in custom_header_groups:

                                case_lines = []

                                case_lines.extend(mechanism_lines)

                                case_lines.extend(header_group)

                                case_lines.append(f"Status code: {status_code}")
                                

                                signature = tuple(case_lines)

                                if signature in seen_cases:
                                    continue

                                seen_cases.add(signature)

                                html_parts.append(
                                    f"""
<div class="case">

<strong>
Case {case_counter}
</strong>

<ul>
"""
                                )

                                case_counter += 1

                                ### Adding the different cases where we observed this result for these Test IDs (numbering and mechanisms set, including status code) ###
                                for line in case_lines:

                                    html_parts.append(
                                        f"""
<li>
{escape(line)}
</li>
"""
                                    )

                                html_parts.append("""
</ul>
</div>
""")

                        ### Adding the specific Deployment IDs where we observed that. ###
                        html_parts.append(
                            f"""
<p>

<strong>
Deployment IDs
({len(deployment_ids)})
</strong>

</p>

<pre>
{escape(deployment_ids)}
</pre>

</div>
"""
                        )

                    html_parts.append("""
</details>
""")

                    ### Detailed Deployments -> ALL raw data mainly for debugging and traceability. ###
                    html_parts.append("""
<details>

<summary>
Detailed Deployments
</summary>
""")

                    for test_id, result_map in cluster["deployments"].items():

                        html_parts.append(
                            f"""
<div class="deployment">

<h4>
Test:
{escape(test_id)}
</h4>
"""
                        )

                        for result, deployments in result_map.items():

                            html_parts.append(
                                f"""
<h5>
Result:
{escape(result)}
</h5>
"""
                            )

                            for dep in deployments:

                                html_parts.append(
                                    f"""
<pre>
deployment_id:
{format_json(dep.get("deployment_id"))}

status_code:
{format_json(dep.get("status_code"))}

run_on:
{format_json(dep.get("run_on"))}

custom_headers:
{format_json(dep.get("custom_headers"))}

mechanisms:
{format_json(dep.get("mechanisms"))}

evidence:
{format_json(dep.get("evidence"))}
</pre>
"""
                                )

                        html_parts.append("""
</div>
""")

                    html_parts.append("""
</details>

</div>
""")

        html_parts.append("""
</div>
""")

    ### Needed JavaScript ###
    html_parts.append("""
<script>

let currentHighlightedTest = null;
let currentBrowser = null;

function showTab(browser)
{
    document
        .querySelectorAll(".tab-content")
        .forEach(el =>
            el.classList.remove("active"));

    document
        .querySelectorAll(".tab-button")
        .forEach(el =>
            el.classList.remove("active"));

    document
        .getElementById(browser)
        .classList.add("active");

    document
        .querySelector(
            `.tab-button[data-browser="${browser}"]`
        )
        .classList.add("active");
                      
    currentBrowser = browser;
}

function jumpToTest(
    browser,
    testId
)
{
    
    const previousBrowser = currentBrowser;
    
    showTab(browser);

    setTimeout(() =>
    {
        const browserTab =
            document.getElementById(browser);

        const target =
            browserTab.querySelector(
                `[data-test-id="${CSS.escape(testId)}"]`
            );

        if (!target)
        {
            showTab(previousBrowser);
            
            alert(
                `"${testId}" not found in ${browser}`
            ); // this happens in cases like: Browser 1 doesn't have a result (None) for a test, but Browsers 2 and 3 have an object. Browsers 2 and 3 differ in a key-value pair of the object, and thus they create an inconsistency, but Browser 1 does not have an object to compare with, so it is not counted at all.

            return;
        }

        if (currentHighlightedTest)
        {
            currentHighlightedTest
                .classList
                .remove(
                    "highlight-test"
                );
        }

        target.classList.add(
            "highlight-test"
        );

        currentHighlightedTest = target;

        const card =
            target.closest(
                ".rule-card"
            );

        target.scrollIntoView({
            behavior: "smooth",
            block: "center"
        });

        card.classList.add(
            "highlight"
        );

        setTimeout(() =>
        {
            card.classList.remove(
                "highlight"
            );
        }, 2000);

    }, 50);
}

</script>

</body>
</html>
""")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))

    print(f"[+] HTML report written to: {output_path}")
