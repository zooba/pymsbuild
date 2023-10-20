#include "pch.h"

using namespace winrt;
using namespace Windows::Foundation;
using namespace Microsoft::UI::Xaml;
using namespace Microsoft::UI::Xaml::Controls;
using namespace Microsoft::UI::Xaml::Navigation;
using IUnk = winrt::Windows::Foundation::IUnknown;
namespace py = pybind11;

template <typename T>
static std::wstring default_repr(const holder<T> &i) {
    return L"<" + std::wstring{winrt::get_class_name(i.v)} + L">";
}

template <typename T>
static auto _ContentControl_Content_get(const holder<T>& o) { return o.v.Content(); }
template <typename T>
static auto _ContentControl_Content_set(holder<T>& o, const holder<IInspectable>& v) { return o.v.Content(v); }

PYBIND11_EMBEDDED_MODULE(_winui_Xaml_Controls, m) {
    py::class_<holder<IInspectable>>(m, "Windows.Foundation.IInspectable")
        .def("__repr__", default_repr<IInspectable>)
    ;

    py::class_<holder<ContentControl>>(m, "Microsoft.UI.Xaml.Controls.ContentControl")
        .def("__repr__", default_repr<ContentControl>)
        .def_property("content", _ContentControl_Content_get<ContentControl>, _ContentControl_Content_set<ContentControl>)
    ;

    py::class_<holder<Button>>(m, "Microsoft.UI.Xaml.Controls.Button")
        .def("__repr__", default_repr<Button>)
        .def_property("content", _ContentControl_Content_get<Button>, _ContentControl_Content_set<Button>)
    ;
}

