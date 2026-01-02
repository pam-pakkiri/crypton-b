module.exports = {
    apps: [
        {
            name: "algo-trade-backend",
            script: "gunicorn",
            args: "-k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000 --workers 4",
            cwd: "./",
            env: {
                PRODUCTION: "1",
                PYTHONPATH: "."
            }
        },
        {
            name: "algo-trade-frontend",
            script: "npm",
            args: "start",
            cwd: "../front-end",
            env: {
                NODE_ENV: "production",
                NEXT_PUBLIC_API_URL: "https://crypton0.com/api",
                NEXT_PUBLIC_WS_URL: "wss://crypton0.com"
            }
        }
    ]
};
