var builder = DistributedApplication.CreateBuilder(args);

var catalog = builder
    .AddJavaScriptApp("catalog", "../services/catalog-api")
    .WithRunScript("dev")
    .WithHttpEndpoint(port: 4310, env: "PORT");

var agent = builder
    .AddJavaScriptApp("agent", "../services/agent-api")
    .WithRunScript("dev")
    .WithHttpEndpoint(port: 4320, env: "PORT")
    .WithReference(catalog)
    .WithEnvironment("CATALOG_API_URL", catalog.GetEndpoint("http"))
    .WaitFor(catalog);

var orders = builder
    .AddPythonApp(
        "orders",
        "../services/order-api",
        "-m",
        "../../.venv",
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4330"])
    .WithPip(install: false)
    .WithHttpEndpoint(targetPort: 4330)
    .WithOtlpExporter();

builder
    .AddViteApp("web", "../apps/web")
    .WithReference(catalog)
    .WithReference(agent)
    .WithReference(orders)
    .WaitFor(catalog)
    .WaitFor(agent)
    .WaitFor(orders)
    .WithExternalHttpEndpoints();

builder.Build().Run();