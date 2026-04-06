module github.com/kumarrajapuvvalla-bit/ops-platform/operator

go 1.22

require (
	k8s.io/api v0.30.1
	k8s.io/apimachinery v0.30.1
	k8s.io/client-go v0.30.1
	sigs.k8s.io/controller-runtime v0.18.2
)

require (
	github.com/go-logr/logr v1.4.1
	github.com/go-logr/zapr v1.3.0
	go.uber.org/zap v1.27.0
)
