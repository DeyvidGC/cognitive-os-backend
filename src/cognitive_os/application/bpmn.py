"""BPMN 2.0 interchange for the observed human process (not executable automation)."""

from xml.etree import ElementTree as ET

from cognitive_os.schemas.recordings import VisualReportContent

NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
    "di": "http://www.omg.org/spec/DD/20100524/DI",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def child(parent, tag, text=None, **attributes):
    prefix, name = tag.split(":")
    element = ET.SubElement(parent, f"{{{NS[prefix]}}}{name}",
                            {key: str(value) for key, value in attributes.items()})
    element.text = text
    return element


def report_bpmn(report):
    content = VisualReportContent.model_validate(report.content)
    root = ET.Element(f"{{{NS['bpmn']}}}definitions", {
        "id": "Definitions", "targetNamespace": "https://cognitive-os.local/bpmn",
        "exporter": "Cognitive OS", "exporterVersion": "1",
    })
    process = child(root, "bpmn:process", id="Process", name=content.title, isExecutable="false")
    child(process, "bpmn:documentation",
          f"Recording {report.recording_id}; revision {report.revision}; {report.review_status}. "
          "Human activities reconstructed from reviewed evidence; not an executable workflow.")
    lane = child(child(process, "bpmn:laneSet", id="Lanes"), "bpmn:lane", id="UserLane", name="Usuario")
    shapes, nodes, flows = {}, {}, []

    def node(identifier, kind, name, bounds, documentation=None):
        element = child(process, f"bpmn:{kind}", id=identifier, name=name)
        if documentation:
            child(element, "bpmn:documentation", documentation)
        if kind == "exclusiveGateway":
            element.set("gatewayDirection", "Diverging")
        child(lane, "bpmn:flowNodeRef", identifier)
        shapes[identifier], nodes[identifier] = bounds, element

    node("start", "startEvent", "Inicio", (322, 70, 36, 36))
    y = 160
    for index, step in enumerate(content.instructions, 1):
        label = step.instruction if len(step.instruction) <= 130 else step.instruction[:127] + "..."
        node(f"step-{index}", "userTask", f"{index}. {label}", (220, y, 240, 110),
             step.instruction + "\nResultado esperado: " + step.expected_result)
        if step.alternatives:
            node(f"decision-{index}", "exclusiveGateway", "", (315, y + 155, 50, 50))
            flows.append((f"step-{index}", f"decision-{index}", None))
            flows.extend((f"decision-{index}", f"step-{branch.target_step}" if branch.target_step else "end",
                          branch.condition) for branch in step.alternatives)
            y += 280 + len(step.alternatives) * 75
        else:
            flows.append((f"step-{index}", f"step-{index + 1}" if index < len(content.instructions) else "end", None))
            y += 190
    node("end", "endEvent", "Fin", (322, y, 36, 36))
    flows.insert(0, ("start", "step-1" if content.instructions else "end", None))
    collaboration = child(root, "bpmn:collaboration", id="Collaboration")
    child(collaboration, "bpmn:participant", id="Participant", name="Proceso observado", processRef="Process")
    plane = child(child(root, "bpmndi:BPMNDiagram", id="Diagram"), "bpmndi:BPMNPlane",
                  id="Plane", bpmnElement="Collaboration")
    width = 900
    for identifier, bounds in {"Participant": (40, 30, width, y + 70),
                               "UserLane": (70, 30, width - 30, y + 70), **shapes}.items():
        shape = child(plane, "bpmndi:BPMNShape", id=f"Shape_{identifier}", bpmnElement=identifier)
        if identifier in {"Participant", "UserLane"}:
            shape.set("isHorizontal", "true")
        if identifier.startswith("decision-"):
            shape.set("isMarkerVisible", "true")
        child(shape, "dc:Bounds", **dict(zip(("x", "y", "width", "height"), bounds)))
    branch_counts = {}
    for index, (source, target, condition) in enumerate(flows):
        identifier = f"Flow_{index}"
        flow = child(process, "bpmn:sequenceFlow", id=identifier, sourceRef=source, targetRef=target)
        if condition:
            flow.set("name", condition if len(condition) <= 45 else condition[:42] + "...")
            child(flow, "bpmn:documentation", condition)
        edge = child(plane, "bpmndi:BPMNEdge", id=f"Edge_{index}", bpmnElement=identifier)
        sx, sy, sw, sh = shapes[source]
        tx, ty, tw, th = shapes[target]
        if condition:
            branch = branch_counts.get(source, 0)
            branch_counts[source] = branch + 1
            # Separate each decision's conditions in a right-hand routing gutter.
            gutter = 550 + branch * 70
            row = sy + 100 + branch * 75
            points = [(sx + sw, sy + sh / 2), (400, sy + sh / 2), (400, row), (gutter, row),
                      (gutter, ty + th / 2), (tx + tw, ty + th / 2)]
        else:
            points = [(sx + sw / 2, sy + sh), (tx + tw / 2, ty)]
        for x, point_y in points:
            child(edge, "di:waypoint", x=x, y=point_y)
        if condition:
            label = child(edge, "bpmndi:BPMNLabel")
            child(label, "dc:Bounds", x=410, y=row - 45, width=130, height=40)
    for identifier, element in nodes.items():
        for index, (_, target, _) in enumerate(flows):
            if target == identifier:
                child(element, "bpmn:incoming", f"Flow_{index}")
        for index, (source, _, _) in enumerate(flows):
            if source == identifier:
                child(element, "bpmn:outgoing", f"Flow_{index}")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
