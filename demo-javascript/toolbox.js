root = "<FileDepot's root URL>"

$.ajaxSetup({ traditional: true });

function render(template_name, data) {
  return Mustache.render($(template_name).html(), data)
}

function api_request(raw_method, url, payload, success, error) {
  method = raw_method.toUpperCase()
  if (method != "GET") {
    payload = JSON.stringify(payload)
  }
  $.ajax({
    url: root + url,
    type: method,
    data: payload,
    success: function(data, textStatus, jqXHR) {
      if (success != undefined) {
        success(data, textStatus, jqXHR)
      }
    },
    error: function(jqXHR, textStatus, errorThrown) {
      if (error != undefined) {
        error(jqXHR, textStatus, errorThrown)
      }
    }
  })
}

function call_api(raw_method, url, payload, success, error) {
  api_request("POST", "login", {"type": "CAS", "cred": {"id": "demo-javascript"}}, function(login_response) {
  session_id = login_response.session_id
  payload["session_id"] = session_id
  api_request(raw_method, url, payload,
    function(data, textStatus, jqXHR) {
      if (success != undefined) {
        success(data, textStatus, jqXHR)
        api_request("POST", "logout", {"session_id": session_id})
      }
    },
    function(jqXHR, textStatus, errorThrown) {
      if (error != undefined) {
        error(jqXHR, textStatus, errorThrown)
        api_request("POST", "logout", {"session_id": session_id})
      }
    }
  )})
}

function upload_to_FileDepot(form_name, callback) {
  file_inputs = $(form_name + " input[type=file]")
  package_request = []
  for (i = 0; i < file_inputs.length; i++) {
    file_input = file_inputs[i].files[0]
    if (file_input != undefined) {
      package_request.push({"name": file_input.name, "type": file_input.type, "size_range": [file_input.size, file_input.size]})
    }
  }

  call_api("POST", "lockers", {"attributes": "pending", "packages": package_request}, function(locker) {
  packages = locker.packages
  unfinished = packages.length
  for (i = 0; i < packages.length; i++) {
    formData = new FormData()
    for (field in packages[i].upload_fields) {
      formData.append(field, packages[i].upload_fields[field])
    }
    formData.append("file", file_inputs[i].files[0])
    $.ajax({
      url: packages[i].upload_url,
      type: "POST",
      data: formData,
      cache: false,
      contentType: false,
      processData: false,
      success: function(upload_response) {
        unfinished -= 1
        if (unfinished == 0 && callback != undefined) {
          callback(locker)
        }
      }
    })
  }})
}

function get_args() {
  var vars = [], hash;
  var hashes = window.location.href.slice(window.location.href.indexOf('?') + 1).split('&');
  for(var i = 0; i < hashes.length; i++) {
    hash = hashes[i].split('=');
    vars.push(hash[0]);
    vars[hash[0]] = hash[1];
  }
  return vars;
}